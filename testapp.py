import threading

import dash.dependencies
from dash import Dash, dcc, html, dash_table, Input, Output, State, callback
import json

import rdflib
import base64
import logging
import requests
import pprint
import os
import pprint
import time
import shutil
import docker
import uuid
import re
import pandas
from dash.exceptions import PreventUpdate
from decouple import config
from rdflib import Graph, URIRef
from SPARQLWrapper import SPARQLWrapper, JSON

app = Dash(__name__)
docker_client = docker.from_env()
api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

appName = "app2"




######## config
SERVER_ENDPOINT = config("SERVER_ENDPOINT", default="http://localhost:8080")
print("SERVER_ENDPOINT is :" + SERVER_ENDPOINT)

META_DATA_ENDPOINT = config("META_DATA_ENDPOINT", default="http://localhost:3030/mydataset")
print("META_DATA_ENDPOINT is : " + META_DATA_ENDPOINT)

ENEXA_SHARED_DIRECTORY = config("ENEXA_SHARED_DIRECTORY", default="/home/shared")
print("ENEXA_SHARED_DIRECTORY is :" + ENEXA_SHARED_DIRECTORY)

META_DATA_GRAPH_NAME = config("META_DATA_GRAPH_NAME", default="http://example.org/meta-data")
print ("META_DATA_GRAPH_NAME is :" + META_DATA_GRAPH_NAME)

ENEXA_WRITEABLE_DIRECTORY = config("ENEXA_WRITEABLE_DIRECTORY", default=ENEXA_SHARED_DIRECTORY + "/experiments")
print("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)

SLEEP_IN_SECONDS = config("SLEEP_IN_SECONDS", default=5, cast=int)
print("SLEEP_IN_SECONDS is :" + str(SLEEP_IN_SECONDS))

EMBEDDINGS_BATCH_SIZE = config("EMBEDDINGS_BATCH_SIZE", default=20, cast=int)
print ("EMBEDDINGS_BATCH_SIZE is :" + str(EMBEDDINGS_BATCH_SIZE))

EMBEDDINGS_DIM = config("EMBEDDINGS_DIM", default=3, cast=int)
print("EMBEDDINGS_DIM is:" + str(EMBEDDINGS_DIM))

EMBEDDINGS_EPOCH_NUM = config("EMBEDDINGS_EPOCH_NUM", default=1, cast=int)
print("EMBEDDINGS_EPOCH_NUM is :" + str(EMBEDDINGS_EPOCH_NUM))

DATASET_NAME_TENTRIS = config("DATASET_NAME_TENTRIS")
print("DATASET_NAME is :" + str(DATASET_NAME_TENTRIS))

# constants
ENEXA_LOGO = "https://raw.githubusercontent.com/EnexaProject/enexaproject.github.io/main/images/enexacontent/enexa_logo_v0.png?raw=true"
ENEXA_EXPERIMENT_SHARED_DIRECTORY_LITERAL = "http://w3id.org/dice-research/enexa/ontology#sharedDirectory"

######## layout

app.layout = html.Div([
    html.Button('test docker log', id='btn-test-docker-log', n_clicks=0),
    html.Label('', id='label-test-docker'),
    html.Button('skip extraction', id='btn-skip-extraction', n_clicks=0),


    html.Label("0", id="levelIndicator"),  ##, style={"display": "none"}
    html.Div(dcc.Input(id='input-on-submit', type='text')),
    html.Button('Submit', id='submit-val', n_clicks=0),
    html.Div(id='container-button-basic',
             children='Enter a value and press submit'),
    dcc.Upload(
        id='upload-data',
        children=html.Button('Upload File'),
        multiple=False,
        style={
            'width': '100%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        }
    ),
    html.Label('status upload ', id= 'lbl-upload-status'),
    html.Div(id='output-data-upload'),
    html.Div([html.Label('status extraction', id='lbl-extraction-status'), html.Button('Start Extraction', id='btn-start-extraction-1', n_clicks=0, disabled=True)], id='level1'),
    html.Div([html.Label('status repair', id='lbl-repair-status'), html.Button('Start Repair', id='btn-start-repair-2', n_clicks=0, disabled=True)], id='level2'),
    html.Div([html.Label('status tentris', id='lbl-tentris-status'), html.Button('Start Tentris', id='btn-start-tentris-3', n_clicks=0, disabled=True)], id='level3'),
    html.Div([html.Label('status tentris', id='lbl-tentris-status1'), html.Button('Start Tentris', id='btn-start-lvl-3', n_clicks=0, disabled=True)], id='level40'),
    html.Div(id='level4'),
    html.Div(id='level5'),
    dcc.Store(id='state-uploadedFile'),
    dcc.Store(id='state-extraction'),
    dcc.Store(id='state-repair'),
    dcc.Store(id='state-tentris')
])


log_container = dcc.Textarea(id='log-container', value='', disabled=True)

######## Methods
def create_experiment_data():
    """
    returns the data of a fresh experiment, with experiment IRI and ...
  """
    response = requests.post(SERVER_ENDPOINT + "/start-experiment", data="", headers={"Content-Type": "application/ld+json", "Accept": "application/ld+json"})
    print(str(response.status_code))
    if response.status_code == 200 or response.status_code == 201:
        print(response.text)

        return {
            "experiment_iri": response.json()["@id"],
            "experiment_folder": response.json()[ENEXA_EXPERIMENT_SHARED_DIRECTORY_LITERAL],
            "raw": response.json()
        }
    else:
        logging.ERROR("error")

    return "http://example.org/experiment1"

def add_module_configuration_to_enexa_service(experiment_resource, relative_file_location_inside_enexa_dir,
                                              uploaded_filename, label_for_addition="File added"):
    logging.info("start add configuration ")
    logging.info("add_module_configuration_to_enexa_service")
    # copy the file in share directory
    logging.info("experiment_resource: " + experiment_resource)
    logging.info("relative_file_location_inside_enexa_dir: " + relative_file_location_inside_enexa_dir)
    logging.info("uploaded_filename: " + uploaded_filename)

    # Split the experimentIRI using "/"
    path_elements = experiment_resource.split("/")

    # Get the last element of the split path
    experimentIRI = path_elements[-1]
    print("experimentIRI is : "+ experimentIRI)

    # if path is not there create it
    path_to_check = os.path.join(ENEXA_SHARED_DIRECTORY,appName ,experimentIRI)

    print("check this path " + path_to_check)
    if not os.path.exists(path_to_check):
        os.makedirs(path_to_check)
    logging.info("copy from "+os.path.join (ENEXA_SHARED_DIRECTORY , uploaded_filename) + " to " + os.path.join(ENEXA_SHARED_DIRECTORY , appName ,experimentIRI  , uploaded_filename))

    shutil.copyfile(os.path.join (ENEXA_SHARED_DIRECTORY , uploaded_filename),
                    os.path.join(ENEXA_SHARED_DIRECTORY , appName ,experimentIRI  , uploaded_filename))
    # add resource
    ttl_for_registering_the_file_upload = """
    @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
    @prefix prov:   <http://www.w3.org/ns/prov#> .

    [] a prov:Entity ; 
        enexa:experiment <{}> ; 
        enexa:location "{}/{}" .
    """.format(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename)

    ttl_for_registering_the_file_upload_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_file_upload)

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld,
                             headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    logging.info("file added and the response is :" + str(response))
    return response

def turtle_to_jsonld(turtle_data):
    """
    transforms RDF Turtle data to JSON-LD
  """
    graph = Graph()
    print("turtle file is as : " + str(turtle_data))
    graph.parse(data=turtle_data, format="turtle")
    return graph.serialize(format="json-ld", indent=2)

def extract_id_from_turtle(turtle_text):
    print ("extract_id_from_turtle input text is :" + turtle_text)
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    print ("graph parsed")
    query = """
            SELECT ?id ?o
            WHERE {
                ?id <http://w3id.org/dice-research/enexa/ontology#experiment> ?o .
            }
        """

    # Execute the query
    results = graph.query(query)
    # Extract and return IDs
    ids = [str(result["id"]) for result in results][0]
    print ("extracted id is : " + ids)
    return ids


def write_file_to_folder(folder, filename, content):
    try:
        print("write_file_to_folder to : " + str(folder))
        print("write_file_to_folder start copy uploaded " + str(filename))
        print(" this content" + content)

        folder = folder.replace("enexa-dir://", ENEXA_SHARED_DIRECTORY + "/")

        print("write_file_to_folder folder is : " + str(folder) + " filename is :" + filename)
        # create directory if not exists
        if not os.path.exists(folder):
            print ("not exist make dir :" + folder)
            os.makedirs(folder)

        file_path = os.path.join(folder, filename)

        # Write the content to the file
        with open(file_path, 'w') as file:
            file.write(content)

    except Exception as exc:
        print (exc)

def add_resource_to_service(experiment_resource, relative_file_location_inside_enexa_dir, file_to_add, label_for_addition="File added"):
    print ("send uploaded file to enexa service ")
    print ("experiment_resource is :" + experiment_resource)
    print ("relative_file_location_inside_enexa_dir is :" + relative_file_location_inside_enexa_dir)
    print ("uploaded_filename is :" + file_to_add)
    ttl_for_registering_the_file_upload = """
  @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
  @prefix prov:   <http://www.w3.org/ns/prov#> .

  [] a prov:Entity ; 
      enexa:experiment <{}> ; 
      enexa:location "{}/{}" .
  """.format(experiment_resource, relative_file_location_inside_enexa_dir, file_to_add)

    ttl_for_registering_the_file_upload_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_file_upload)

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld,
                                 headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    print("file added and the response is :" + str(response))
    return response


def start_extraction_module(experiment_resource, urls_to_process_iri, configFile_iri):
    """
    creates a message for starting a module instance

    be aware that	http://w3id.org/dice-research/enexa/module/extraction/parameter/urls_to_process is a hard-coded parameter for the module expressing the property for the input data (JSON file)
  """
    start_module_message = """
@prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
alg:instanceOf <http://w3id.org/dice-research/enexa/module/extraction/1.0.0> ;
<http://w3id.org/dice-research/enexa/module/extraction/parameter/urls_to_process> <{}>;
<http://w3id.org/dice-research/enexa/module/extraction/parameter/path_generation_parameters> <{}>.
""".format(experiment_resource, urls_to_process_iri, configFile_iri)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def extract_X_from_turtle(turtle_text, x):
    print("turtle_text is :" + str(turtle_text))
    print("x is :" + str(x))
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    query = "SELECT ?id ?o \n WHERE { \n ?id <" + x + "> ?o .\n }"
    # st.info(query)
    # Execute the query
    results = graph.query(query)
    # Extract and return IDs
    o = [str(result["o"]) for result in results][0]
    print ("extracted X is : " + o)
    return o


def extract_id_from_turtle(turtle_text):
    print ("extract_id_from_turtle input text is :" + turtle_text)
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    print ("graph parsed")
    query = """
            SELECT ?id ?o
            WHERE {
                ?id <http://w3id.org/dice-research/enexa/ontology#experiment> ?o .
            }
        """

    # Execute the query
    results = graph.query(query)
    # Extract and return IDs
    ids = [str(result["id"]) for result in results][0]
    print ("extracted id is : " + ids)
    return ids

# Function to read and append logs to the log_container
#def read_and_append_logs(stream, log_container):

    #for line in stream:
    #    # Append the log line to the log_container
    #    log_container.value += line.decode('utf-8') + '\n'
def print_container_logs(container_id):
    try:
        print('logs for docker ')
        # Use the APIClient object to access the logs() method
        stream  = api_client.logs(stream=True, follow=True)
        # Iterate over the log stream and print logs until the container exits
        for line in stream:
            print(line.decode('utf-8').strip())
        #stream = api_client.logs(container=container_id, follow=False)
        ## Create a thread to continuously read and append logs to the log_container
        #thread = threading.Thread(target=read_and_append_logs, args=(stream, log_container))
        #thread.start()
    except docker.errors.APIError as e:
        print(f"Error accessing container logs: {e}")

def extract_X_from_triplestore_old(X, triple_store_endpoint, graph_name, module_instance_iri):
    #st.info("extract_X_from_triplestore"+str(module_instance_iri))
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <" + X + "> ?iri. } }"
    print(query_str)
    sparql.setQuery(query_str)
    print("0")
    sparql.setReturnFormat('json')
    print("1")
    results = sparql.query().convert()
    print("2")
    returnIRI = ""
    for result in results["results"]["bindings"]:
        returnIRI = result["iri"]["value"]

    print("3")
    if returnIRI == "":
        logging.error(
            "there is no iri in the triple store for <{"
            "}><" + X + ">").format(
            module_instance_iri)
    else:
        return returnIRI

def extract_X_from_triplestore(X, triple_store_endpoint, graph_name, module_instance_iri):
    print(X)
    print(triple_store_endpoint)
    print(graph_name)
    print(module_instance_iri)
    try:
        g = Graph()
        sparql = SPARQLWrapper(triple_store_endpoint)
        query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <" + X + "> ?iri. } }"

        print(query_str)  # For debugging purposes

        sparql.setQuery(query_str)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        returnIRI = ""
        for result in results["results"]["bindings"]:
            returnIRI = result["iri"]["value"]

        if returnIRI == "":
            logging.error(
                f"There is no iri in the triple store for <{module_instance_iri}><{X}>"
            )
        else:
            return returnIRI

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        # Raise the exception again if you want to handle it elsewhere
        raise

def read_file(file_path, num_lines):
    try:
        with open(file_path, 'r') as in_file:
            all_lines = in_file.readlines()
        return all_lines[:num_lines]
    except Exception as e:
        return [str(e)]

def get_the_status(SERVER_ENDPOINT, module_instance_iri, experiment_resource):
    status_container_endpoint = SERVER_ENDPOINT + "/container-status"
    status_module_message_as_json  = {
        "moduleInstanceIRI": module_instance_iri,
        "experimentResource": experiment_resource
    }
    #st.info(json.dumps(status_module_message_as_json))
    return requests.post(status_container_endpoint, data=json.dumps(status_module_message_as_json),
                                          headers={"Content-Type": "application/json", "Accept": "text/turtle"})

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    return decoded.decode('utf-8')

def start_kg_fixing_module(experiment_resource, module_instance_id, second_step_responce_configFile_resource):
    print("start_kg_fixing_module")
    print("experiment_resource :" + experiment_resource)
    print("module_instance_id :" + module_instance_id)
    print("second_step_responce_configFile_resource :" + second_step_responce_configFile_resource)

    start_module_message = """
@prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
alg:instanceOf <http://w3id.org/dice-research/enexa/module/kg-fixing/1.0.0> ;
<http://w3id.org/dice-research/enexa/module/kg-fixing/parameter/a-boxFile> <{}>;
<http://w3id.org/dice-research/enexa/module/kg-fixing/parameter/t-boxFile> <{}>.
""".format(experiment_resource, module_instance_id, second_step_responce_configFile_resource)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module

def start_tentris_module(experiment_resource, wikidata5m_unfiltered_iri):
    start_module_message = """
    @prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
    @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
    @prefix prov:   <http://www.w3.org/ns/prov#> .
    @prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
    @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    [] rdf:type enexa:ModuleInstance ;
    enexa:experiment <{}> ;
    alg:instanceOf <http://w3id.org/dice-research/enexa/module/tentris/0.2.0-SNAPSHOT-1> ;
    <http://w3id.org/dice-research/enexa/module/tentris/parameter/file> <{}>.
    """.format(experiment_resource, wikidata5m_unfiltered_iri)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module

logs = []
def update_ui(line):
    print(line)
    # Update the UI with the new log line
    logs.append(line)
    app.layout = html.Div(children=[
        html.Output('docker-logs', 'children'),
        html.Mark('Docker logs:')
    ])

def read_container_logs_stop_when_reach_x(container_id, x):
    # st.info("looking for "+x)
    returnlines = []
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        for log_line in container.logs(stream=True):
            update_ui(log_line)
            if x in str(log_line.decode("utf-8")):
                return
    except docker.errors.NotFound:
        logging.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        logging.error("An error occurred: " + str(e))
    return returnlines
######## Steps

## upload file ---------------------------------------------------------------------------------------------------------

@app.callback([
    Output('btn-start-extraction-1', "disabled", allow_duplicate=True),
    Output('lbl-upload-status', "children", allow_duplicate=True),
    Output('output-data-upload', 'children'),
    Output('state-uploadedFile', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')],
    prevent_initial_call=True
)
def file_uploaded(contents,filename):
    if contents is None:
        return True, "error", "there is error", {}
    else:
        content = parse_contents(contents)
        print(content)
        print(filename)
        # create experiment instance
        experiment_data = create_experiment_data()
        print("0")
        experiment_resource = experiment_data["experiment_iri"]
        experiment_directory = experiment_data["experiment_folder"]

        relative_file_location_inside_enexa_dir = experiment_directory

        # add resource config file
        # experiment_resource, relative_file_location_inside_enexa_dir,uploaded_filename
        print("1")
        responce_configFile_resource = add_module_configuration_to_enexa_service(experiment_resource,
                                                                                 relative_file_location_inside_enexa_dir,
                                                                                 "generation_parameters.json",
                                                                                 label_for_addition="Adding extraction parameters file")
        print("2")
        if responce_configFile_resource.status_code != 200:
            logging.error("error in upload configuration file ")
        else:
            generation_parameters_IRI = extract_id_from_turtle(responce_configFile_resource.text)
            print("4")
            #TODO: add file name
            uploaded_filename = filename #str(uuid.uuid4())
            uploaded_file_content = content

            # UI file upload
            write_file_to_folder(ENEXA_WRITEABLE_DIRECTORY, uploaded_filename, uploaded_file_content)
            print("File {} uploaded successfully and stored in experiment's directory: {}".format(uploaded_filename,
                                                                                                  ENEXA_WRITEABLE_DIRECTORY))

            write_file_to_folder(relative_file_location_inside_enexa_dir, uploaded_filename, uploaded_file_content)

            response_adding_uploaded_file = add_resource_to_service(experiment_resource,
                                                                    relative_file_location_inside_enexa_dir,
                                                                    uploaded_filename,
                                                                    label_for_addition="Adding file with uploaded URLs")
            if response_adding_uploaded_file.status_code != 200:
                logging.error("Error while registering ENEXA configuration file upload. :cry:")
                logging.error(response_adding_uploaded_file.status_code + " " + str(response_adding_uploaded_file))
            else:
                urls_to_process_iri = extract_id_from_turtle(response_adding_uploaded_file.text)
                return False, "ready", uploaded_file_content, {'content': uploaded_file_content, 'experiment_resource': experiment_resource, 'urls_to_process_iri': urls_to_process_iri, 'generation_parameters_IRI': generation_parameters_IRI}

## start extraction ----------------------------------------------------------------------------------------------------

@app.callback(
    [Output('btn-start-repair-2', "disabled" , allow_duplicate=True),
    Output('lbl-extraction-status', 'children'),
    Output('state-extraction', 'data')],
    [Input('btn-start-extraction-1', 'n_clicks'),Input('state-uploadedFile','data')],
    prevent_initial_call=True
)
def start_extraction_step(n_clicks, data):
    print("dataXX")
    print(n_clicks)
    print(data)
    if(n_clicks==1):
                print("Starting extraction module ...")
                experiment_resource = data['experiment_resource']
                print(experiment_resource)
                urls_to_process_iri = data['urls_to_process_iri']
                print(urls_to_process_iri)
                generation_parameters_IRI = data['generation_parameters_IRI']
                print(generation_parameters_IRI)

                response_start_module = start_extraction_module(experiment_resource, urls_to_process_iri,
                                                                    generation_parameters_IRI)

                print(str(response_start_module.status_code))
                if response_start_module.status_code != 200:
                    logging.error("Error while starting ENEXA task: {}.".format(response_start_module))
                else:
                    print(str(response_start_module))

                    module_instance_iri = extract_id_from_turtle(response_start_module.text)
                    container_id = extract_X_from_turtle(response_start_module.text,
                                                         "http://w3id.org/dice-research/enexa/ontology#containerId")

                    logging.info("container_id is : " + container_id)

                    response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                           module_instance_iri,
                                                                           experiment_resource)
                    print("status is : " + response_check_module_instance_status.text)

                    # ask for status of the module instance until it is finished
                    elapsedTime = SLEEP_IN_SECONDS
                    while "exited" not in response_check_module_instance_status.text:
                        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                               module_instance_iri,
                                                                               experiment_resource)
                        print("status is : " + response_check_module_instance_status.text)
                        time.sleep(SLEEP_IN_SECONDS)
                        elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                        # Update the text of the info box in the session state
                        # st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)


                    #todo check if it was successful
                    extracted_file_iri = extract_X_from_triplestore(
                        "http://w3id.org/dice-research/enexa/module/extraction/result/triples", META_DATA_ENDPOINT,
                        META_DATA_GRAPH_NAME,
                        module_instance_iri)

                    file_path = extract_X_from_triplestore(
                        "http://w3id.org/dice-research/enexa/ontology#location", META_DATA_ENDPOINT,
                        META_DATA_GRAPH_NAME,
                        extracted_file_iri)
                    file_path = file_path.replace("enexa-dir:/", ENEXA_SHARED_DIRECTORY)

                    # lines = read_file(file_path, 200, "BASF")
                    lines = read_file(file_path, 200)
                    # single_string = "\n".join(lines)
                    # file_content = ""
                    # for line in lines :
                    #     file_content += line




                    print('done!')
                    return False, "extraction done", {'experiment_resource':experiment_resource,'extracted_file_iri':extracted_file_iri}
    else:
        raise PreventUpdate
## start repair ----------------------------------------------------------------------------------------------------
@app.callback(
        [Output('btn-start-tentris-3', "disabled", allow_duplicate=True),
         Output('lbl-repair-status', 'children'),
         Output('state-repair', 'data')],
        [Input('btn-start-repair-2', 'n_clicks'), Input('state-extraction','data')],
        prevent_initial_call=True
)
def start_repair_step(n_clicks, data):
        if(n_clicks==1):
            experiment_resource = data['experiment_resource']
            extracted_file_iri = data['extracted_file_iri']

            second_step_experiment_data = create_experiment_data()
            second_step_experiment_resource = second_step_experiment_data["experiment_iri"]
            second_step_experiment_directory = second_step_experiment_data["experiment_folder"]
            second_step_relative_file_location_inside_enexa_dir = second_step_experiment_directory

            second_step_responce_configFile_resource = add_module_configuration_to_enexa_service(
                second_step_experiment_resource,
                second_step_relative_file_location_inside_enexa_dir,
                "1-ontology_version_1.ttl",
                label_for_addition="Adding ontology file")

            if (second_step_responce_configFile_resource.status_code != 200):
                logging.error("cannot add file")
            else:
                # st.info("T-box file add " + second_step_responce_configFile_resource.text + " ")
                print('file add ')
                uploadedFileId = extract_id_from_turtle(second_step_responce_configFile_resource.text)
                print('file id is  ' + str(uploadedFileId))

                response_second_step = start_kg_fixing_module(experiment_resource, extracted_file_iri, uploadedFileId)

                if response_second_step.status_code != 200:
                    logging.error("Error while starting Knowldge Graph Fixing  ")
                else:
                    second_step_module_instance_iri = extract_id_from_turtle(response_second_step.text)
                    if second_step_module_instance_iri:
                        print("id:", second_step_module_instance_iri)
                    else:
                        print("No id found in JSON-LD")

                    module_instance_iri = extract_id_from_turtle(response_second_step.text)

                    container_id_fixing_module = extract_X_from_turtle(response_second_step.text,
                                                                       "http://w3id.org/dice-research/enexa/ontology#containerId")

                    #changedlines = print_container_logs(container_id_fixing_module)

                    response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                           module_instance_iri,
                                                                           experiment_resource)
                    print("status is : " + response_check_module_instance_status.text)

                    # ask for status of the module instance until it is finished
                    elapsedTime = SLEEP_IN_SECONDS
                    while "exited" not in response_check_module_instance_status.text:
                        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                               module_instance_iri,
                                                                               experiment_resource)
                        print("status is : " + response_check_module_instance_status.text)
                        time.sleep(SLEEP_IN_SECONDS)
                        elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                        # Update the text of the info box in the session state
                        # st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

                    # skip embeddings
                    repaired_a_box_iri = extract_id_from_turtle(response_second_step.text)

                    return False,"done",{'experiment_resource':experiment_resource, 'repaired_a_box_iri':repaired_a_box_iri}

                #start_tentris(experiment_resource, repaired_a_box_iri)
        else:
            raise PreventUpdate

## start tentris ----------------------------------------------------------------------------------------------------
@app.callback(
        [Output('btn-start-lvl-3', "disabled", allow_duplicate=True),
         Output('lbl-tentris-status', 'children'),
         Output('state-tentris', 'data')],
        [Input('btn-start-tentris-3', 'n_clicks'), Input('state-repair','data')],
        prevent_initial_call=True
)
def start_tentris_step(n_clicks, data):
    if(n_clicks==1):
        experiment_resource = data['experiment_resource']
        print(experiment_resource)
        repaired_a_box_iri = data['repaired_a_box_iri']
        print(repaired_a_box_iri)

    else:
        raise PreventUpdate

## level 1
@app.callback(
    Output("btn-start-repair-2", "disabled"),
    Output("level1", "children"),
    Input("lbl-extraction-status", "n_clicks"),
    prevent_initial_call=True
)
def update_buttons(button_1_clicks):
    if button_1_clicks == 1:
        return False, "First button clicked. Second button is now active."


## level 2  ###########################################################################################################


## level 3  ###########################################################################################################


## level 4  ###########################################################################################################

@callback(
    Output('container-button-basic', 'children'),
    Input('submit-val', 'n_clicks'),
    State('input-on-submit', 'value'),
    prevent_initial_call=True
)
def update_output(n_clicks, value):
    extracted_file_iri = extract_X_from_triplestore(
        "http://w3id.org/dice-research/enexa/module/extraction/result/triples", META_DATA_ENDPOINT,
        META_DATA_GRAPH_NAME,
        "http://example.org/enexa/373f38f2-fe94-42ca-8d4e-abbf022f8132")
    print(extracted_file_iri)
    return 'The input value was "{}" and the button has been clicked {} times'.format(
        value,
        n_clicks
    )


@callback(
[Output('btn-start-extraction-1', "disabled", allow_duplicate=True),
    Output('btn-start-repair-2', "disabled", allow_duplicate=True),
     Output('lbl-extraction-status', 'children',allow_duplicate=True),
     Output('state-extraction', 'data',allow_duplicate=True)],
    [Input('btn-skip-extraction','n_clicks')],
    prevent_initial_call=True
)
def skipEx(n_clicks):
    if(n_clicks == 1):
        return True, False,'skipped', {'experiment_resource':'http://example.org/enexa/6c8231ba-6129-459a-9989-fa3d2f4530cb','extracted_file_iri':'http://example.org/enexa/db37f350-aeeb-49e3-ae19-3c75d94b2349'}
    else :
        raise PreventUpdate


# Define the 'another-callback' callback
@app.callback(
    Output('label-test-docker', 'children'),
    [dash.dependencies.Input('another-callback', 'triggered')],
    suppress_callback_exceptions=True
)
def update_another_output():
    print('kkk')
    # Simulate a long-running operation
    time.sleep(2)
    return "FF"

@callback(
Output('label-test-docker', 'children'),
    [Input('btn-test-docker-log', 'n_clicks')],
    prevent_initial_call=True
)
def test_docker_log(n_clicks):
    if(n_clicks == 1):
        app.callback_context.trigger('another-callback')
    elif (n_clicks == 2):
        experiment_resource = 'http://example.org/enexa/6c8231ba-6129-459a-9989-fa3d2f4530cb'
        repaired_a_box_iri = 'http://example.org/enexa/1fada534-be3e-4176-8b62-1a62e0d24c59'

        tentris_experiment_data = create_experiment_data()
        tentris_experiment_resource = tentris_experiment_data["experiment_iri"]
        tentris_experiment_directory = tentris_experiment_data["experiment_folder"]
        tentris_relative_file_location_inside_enexa_dir = tentris_experiment_directory

        # add wikidata5m
        responce_add_wikidata5m = add_module_configuration_to_enexa_service(
            tentris_experiment_resource,
            tentris_relative_file_location_inside_enexa_dir,
            DATASET_NAME_TENTRIS,
            label_for_addition="Adding Wikidata5M dataset file")
        if (responce_add_wikidata5m.status_code != 200):
            logging.error("cannot add file: " + DATASET_NAME_TENTRIS)
        else:
            # st.info("data set add to service " + responce_add_wikidata5m.text + " ")

            wikidata5m_unfiltered_iri = extract_id_from_turtle(responce_add_wikidata5m.text)

            response_tentris_step = start_tentris_module(experiment_resource, wikidata5m_unfiltered_iri)

            container_id_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
                                                                       "http://w3id.org/dice-research/enexa/ontology#containerId")

            container_name_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
                                                                         "http://w3id.org/dice-research/enexa/ontology#containerName")

            read_container_logs_stop_when_reach_x(container_id_tentris_step_deployed, "0.0.0.0:9080")
        return "XX"
    else :
        return "nothing"



if __name__ == '__main__':
    app.run(debug=True)
