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
from tabulate import tabulate

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
print("META_DATA_GRAPH_NAME is :" + META_DATA_GRAPH_NAME)

ENEXA_WRITEABLE_DIRECTORY = config("ENEXA_WRITEABLE_DIRECTORY", default=ENEXA_SHARED_DIRECTORY + "/experiments")
print("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)

SLEEP_IN_SECONDS = config("SLEEP_IN_SECONDS", default=5, cast=int)
print("SLEEP_IN_SECONDS is :" + str(SLEEP_IN_SECONDS))

EMBEDDINGS_BATCH_SIZE = config("EMBEDDINGS_BATCH_SIZE", default=20, cast=int)
print("EMBEDDINGS_BATCH_SIZE is :" + str(EMBEDDINGS_BATCH_SIZE))

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
    # html.Button('test docker log', id='btn-test-docker-log', n_clicks=0),
    # html.Label('', id='label-test-docker'),
    # html.Button('skip extraction', id='btn-skip-extraction', n_clicks=0),
    #
    #
    # html.Label("0", id="levelIndicator"),  ##, style={"display": "none"}
    # html.Div(dcc.Input(id='input-on-submit', type='text')),
    # html.Button('Submit', id='submit-val', n_clicks=0),
    # html.Div(id='container-button-basic',
    #          children='Enter a value and press submit'),
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
    html.Label('No file has been uploaded', id='lbl-upload-status'),
    html.Div([html.Button('Start Extraction', id='btn-start-extraction-1', n_clicks=0, disabled=True),
              html.Label('The extraction step has not started yet', id='lbl-extraction-status')], id='level1'),
    dcc.Interval(
        id='interval-component-extraction',
        interval=3 * 1000,  # in milliseconds
        n_intervals=0,
        disabled=True
    ),
    dcc.Textarea(id='extraction_docker_log', value='', readOnly=True, style={'width': '100%', 'height': '300px'}),
    dcc.Store(id='extraction_afterrun_state'),
    html.Div([html.Button('Start Repair', id='btn-start-repair-2', n_clicks=0, disabled=True),
              html.Label('The repair step has not started yet', id='lbl-repair-status')], id='level2'),
    html.Div([html.Button('Start Tentris', id='btn-start-tentris-3', n_clicks=0, disabled=True),
              html.Label('The Tentris has not started yet', id='lbl-tentris-status')], id='level3'),
    # html.Div([html.Label('status tentris', id='lbl-tentris-status1'), html.Button('Start Tentris', id='btn-start-lvl-3', n_clicks=0, disabled=True)], id='level40'),
    html.Div(id='level4'),
    html.Div(id='level5'),
    dcc.Store(id='state-uploadedFile'),
    dcc.Store(id='state-extraction'),
    dcc.Store(id='state-repair'),
    dcc.Store(id='state-tentris'),
    dcc.Interval(
        id='interval-component-tentris',
        interval=3 * 1000,  # in milliseconds
        n_intervals=0,
        disabled=True
    ),
    dcc.Textarea(id='tentris_docker_log', value='', readOnly=True, style={'width': '100%', 'height': '300px'}),
    html.Div([html.Button('Start Tentris filtering 5m file', id='btn-start-filter-5m', n_clicks=0, disabled=True),
              html.Label('Filtering does not start yet ', id='lbl-tentris-filter-status')], id='levelfilter5m'),
    dcc.Store(id='state-tentris-filter'),
    html.Div([html.Button('Start CEL transform', id='btn-start-cel-transform', n_clicks=0, disabled=True),
              html.Label('The transformation of the data for CEL has not started yet', id='lbl-cel-transform-status')],
             id='levelceltransform'),
    dcc.Store(id='state-cel-transform'),
    html.Div([html.Button('Start CEL', id='btn-start-cel', n_clicks=0, disabled=True),
              html.Label('The CEL step has not started yet.', id='lbl-cel-status')], id='levelcel'),
    dcc.Interval(
        id='interval-component-cel',
        interval=3 * 1000,  # in milliseconds
        n_intervals=0,
        disabled=True
    ),
    dcc.Store(id='state-cel'),
    dcc.Textarea(id='cel_docker_log', value='', readOnly=True, style={'width': '100%', 'height': '300px'}),
    dcc.Store(id='cel_afterrun_state'),
    html.Div([html.Button('Start CEL Server', id='btn-start-cel-server', n_clicks=0, disabled=True),
              html.Label('The server for CEL has not started yet', id='lbl-cel-serve')], id='levelcelserv'),
    dcc.Interval(
        id='interval-component-cel-serve',
        interval=3 * 1000,  # in milliseconds
        n_intervals=0,
        disabled=True
    ),
    dcc.Textarea(id='cel_serve_docker_log', value='', readOnly=True, style={'width': '100%', 'height': '300px'}),
    html.Div([html.Button('send examples 1', id='btn_cel_example_1', n_clicks=0, disabled=True)]),
    dcc.Textarea(id='txt_result_example_1', value='', readOnly=True, style={'width': '100%', 'height': '200px'}),
    html.Div([html.Button('send examples 2', id='btn_cel_example_2', n_clicks=0, disabled=True)]),
    dcc.Textarea(id='txt_result_example_2', value='', readOnly=True, style={'width': '100%', 'height': '200px'}),
    html.Div([html.Button('send examples 3', id='btn_cel_example_3', n_clicks=0, disabled=True)]),
    dcc.Textarea(id='txt_result_example_3', value='', readOnly=True, style={'width': '100%', 'height': '200px'}),
    html.Div([html.Button('send examples 4', id='btn_cel_example_4', n_clicks=0, disabled=True)]),
    dcc.Textarea(id='txt_result_example_4', value='', readOnly=True, style={'width': '100%', 'height': '200px'}),
    html.Div(dcc.Input(id='input-on-submit', type='text')),
    html.Button('Submit', id='submit-val', n_clicks=0),
    html.Label("", id="levelIndicator"),  ##, style={"display": "none"}
])

log_container = dcc.Textarea(id='log-container', value='', disabled=True)


######## Methods
def create_experiment_data():
    """
    returns the data of a fresh experiment, with experiment IRI and ...
  """
    response = requests.post(SERVER_ENDPOINT + "/start-experiment", data="",
                             headers={"Content-Type": "application/ld+json", "Accept": "application/ld+json"})
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
    print("experimentIRI is : " + experimentIRI)

    # if path is not there create it
    path_to_check = os.path.join(ENEXA_SHARED_DIRECTORY, appName, experimentIRI)

    print("check this path " + path_to_check)
    if not os.path.exists(path_to_check):
        os.makedirs(path_to_check)
    logging.info("copy from " + os.path.join(ENEXA_SHARED_DIRECTORY, uploaded_filename) + " to " + os.path.join(
        ENEXA_SHARED_DIRECTORY, appName, experimentIRI, uploaded_filename))

    shutil.copyfile(os.path.join(ENEXA_SHARED_DIRECTORY, uploaded_filename),
                    os.path.join(ENEXA_SHARED_DIRECTORY, appName, experimentIRI, uploaded_filename))
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
    print("extract_id_from_turtle input text is :" + turtle_text)
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    print("graph parsed")
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
    print("extracted id is : " + ids)
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
            print("not exist make dir :" + folder)
            os.makedirs(folder)

        file_path = os.path.join(folder, filename)

        # Write the content to the file
        with open(file_path, 'w') as file:
            file.write(content)

    except Exception as exc:
        print(exc)


def add_resource_to_service(experiment_resource, relative_file_location_inside_enexa_dir, file_to_add,
                            label_for_addition="File added"):
    print("send uploaded file to enexa service ")
    print("experiment_resource is :" + experiment_resource)
    print("relative_file_location_inside_enexa_dir is :" + relative_file_location_inside_enexa_dir)
    print("uploaded_filename is :" + file_to_add)
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
    print("extracted X is : " + o)
    return o


def extract_id_from_turtle(turtle_text):
    print("extract_id_from_turtle input text is :" + turtle_text)
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    print("graph parsed")
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
    print("extracted id is : " + ids)
    return ids


# Function to read and append logs to the log_container
# def read_and_append_logs(stream, log_container):

# for line in stream:
#    # Append the log line to the log_container
#    log_container.value += line.decode('utf-8') + '\n'
def print_container_logs_old(container_id):
    try:
        print('logs for docker ')
        # Use the APIClient object to access the logs() method
        stream = api_client.logs(stream=True, follow=True)
        # Iterate over the log stream and print logs until the container exits
        for line in stream:
            print(line.decode('utf-8').strip())
        # stream = api_client.logs(container=container_id, follow=False)
        ## Create a thread to continuously read and append logs to the log_container
        # thread = threading.Thread(target=read_and_append_logs, args=(stream, log_container))
        # thread.start()
    except docker.errors.APIError as e:
        print(f"Error accessing container logs: {e}")


def extract_X_from_triplestore_old(X, triple_store_endpoint, graph_name, module_instance_iri):
    # st.info("extract_X_from_triplestore"+str(module_instance_iri))
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
    status_module_message_as_json = {
        "moduleInstanceIRI": module_instance_iri,
        "experimentIRI": experiment_resource
    }
    # st.info(json.dumps(status_module_message_as_json))
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


def read_container_logs(container_id):
    returnlines = []
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)

        # Retrieve existing logs
        existing_logs = container.logs().decode('utf-8').split('\n')
        returnlines.extend(map(str, existing_logs))

        # Stream new logs
        for log_line in container.logs(stream=True, follow=False):
            returnlines.append(str(log_line.decode('utf-8')))
            print(log_line.decode('utf-8'))
    except docker.errors.NotFound:
        logging.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        logging.error("An error occurred: " + str(e))

    return returnlines


def read_container_logs_old(container_id):
    returnlines = []
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)

        # Retrieve existing logs
        existing_logs = container.logs().decode('utf-8').split('\n')
        returnlines.extend(existing_logs)

        # Stream new logs
        for log_line in container.logs(stream=True, follow=False):
            returnlines.append(str(log_line.decode('utf-8')))
            print(log_line.decode('utf-8'))
    except docker.errors.NotFound:
        logging.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        logging.error("An error occurred: " + str(e))

    return returnlines


def read_container_logs_stop_when_reach_x(container_id, x):
    returnlines = []
    is_finished = False
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)

        # Retrieve existing logs
        existing_logs = container.logs().decode('utf-8').split('\n')
        returnlines.extend(existing_logs)

        # Stream new logs
        for log_line in container.logs(stream=True, follow=False):
            returnlines.append(log_line.decode('utf-8'))
            print(log_line.decode('utf-8'))
            if x in log_line.decode('utf-8'):
                is_finished = True
                break  # Stop streaming logs if x is found
    except docker.errors.NotFound:
        logging.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        logging.error("An error occurred: " + str(e))

    return returnlines, is_finished


def old_read_container_logs_stop_when_reach_x(container_id, x):
    # st.info("looking for "+x)
    returnlines = []
    is_finished = False
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        for log_line in container.logs(stream=True):
            returnlines.append(log_line)
            print(log_line)
            if x in str(log_line):
                is_finished = True
    except docker.errors.NotFound:
        logging.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        logging.error("An error occurred: " + str(e))
    return returnlines, is_finished


def run_query_triplestore_subject(query_str, triple_store_endpoint, s):
    g = Graph()
    # st.info("triple store endpoint is :"+triple_store_endpoint)
    sparql = SPARQLWrapper(triple_store_endpoint)
    print("query is :" + query_str)
    print("endpoint is :" + triple_store_endpoint)
    # st.info(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()

    # st.info(str(results))

    for result in results["results"]["bindings"]:
        p = result["p"]["value"]
        # st.info("p is :"+str(p))
        o = result["o"]["value"]
        # st.info("o is :" + str(o))

        g.add((rdflib.term.URIRef(s), rdflib.term.URIRef(str(p)), rdflib.term.URIRef(str(o))))

    num_triples = len(g)

    # st.success("graph size is : " + str(num_triples))
    return g


def run_query_triplestore_object(query_str, triple_store_endpoint, o):
    g = Graph()
    # st.info("triple store endpoint is :"+triple_store_endpoint)
    sparql = SPARQLWrapper(triple_store_endpoint)
    print("query is :" + query_str)
    print("endpoint is :" + triple_store_endpoint)
    # st.info(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()

    # st.info(str(results))

    for result in results["results"]["bindings"]:
        p = result["p"]["value"]
        # st.info("p is :" + str(p))
        s = result["s"]["value"]
        # st.info("s is :" + str(s))

        g.add((rdflib.term.URIRef(str(s)), rdflib.term.URIRef(str(p)), rdflib.term.URIRef(o)))

    # num_triples = len(g)

    # st.success("graph size is : " + str(num_triples))
    return g


def start_cel_transform_module(experiment_resource, nt_file_iri, second_input):
    print("start_cel_transform_module")
    print("experiment_resource : " + experiment_resource)
    print("nt_file_iri : " + nt_file_iri)

    start_module_message = """
@prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
alg:instanceOf <http://w3id.org/dice-research/enexa/module/transform/0.0.1> ;
<http://w3id.org/dice-research/enexa/module/transform/parameter/input> <{}>;
<http://w3id.org/dice-research/enexa/module/transform/parameter/input> <{}>;
<http://w3id.org/dice-research/enexa/module/transform/parameter/outputMediaType> <https://www.iana.org/assignments/media-types/application/owl+xml>.
""".format(experiment_resource, nt_file_iri, second_input)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    # st.info("start_module_message_as_jsonld : "+start_module_message_as_jsonld)

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})

    # st.info("responce is "+ response_start_module.text )
    # st.info("responce status is "+ str(response_start_module.status_code))
    return response_start_module


def extract_output_from_triplestore(triple_store_endpoint, graph_name, module_instance_iri):
    print("extract_output_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <http://w3id.org/dice-research/enexa/module/transform/result/output> ?iri. } }"
    print(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()
    returnIRI = ""
    for result in results["results"]["bindings"]:
        returnIRI = result["iri"]["value"]

    if returnIRI == "":
        logging.error(
            "there is no iri in the triple store for <" + module_instance_iri + "><http://w3id.org/dice-research/enexa/module/transform/result/output>")
    else:
        return returnIRI


def start_cel_module(experiment_resource, owl_file_iri, embedding_csv_iri):
    print("start_cel_module")
    print("experiment_resource: " + str(experiment_resource))
    print("owl_file_iri : " + str(owl_file_iri))
    print("embedding_csv_iri : " + str(embedding_csv_iri))

    start_module_message = """
    @prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
    @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
    @prefix prov:   <http://www.w3.org/ns/prov#> .
    @prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
    @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
    [] rdf:type enexa:ModuleInstance ;
    enexa:experiment <{}> ;
    alg:instanceOf <http://w3id.org/dice-research/enexa/module/cel-train/1.0.0> ;
    <http://w3id.org/dice-research/enexa/module/cel-train/parameter/kg> <{}>;
    <http://w3id.org/dice-research/enexa/module/cel-train/parameter/kge> <{}>.
    """.format(experiment_resource, owl_file_iri, embedding_csv_iri)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def extract_cel_trained_kge_from_triplestore(triple_store_endpoint, graph_name, module_instance_iri):
    print("extract_cel_trained_kge_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <http://w3id.org/dice-research/enexa/module/cel-train/result/heuristics> ?iri. } }"
    print(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()
    returnIRI = ""
    for result in results["results"]["bindings"]:
        returnIRI = result["iri"]["value"]

    if returnIRI == "":
        logging.error(
            "there is no iri in the triple store for <{"
            "}><http://w3id.org/dice-research/enexa/module/transform/result/output>").format(
            module_instance_iri)
    else:
        return returnIRI


def start_cel_service_module(experiment_resource, owl_file_iri, embedding_csv_iri, cel_trained_file_kge_iri):
    print("start_cel_service_module")
    print("experiment_resource : " + experiment_resource)
    print("owl_file_iri : " + owl_file_iri)
    print("embedding_csv_iri : " + embedding_csv_iri)
    print("cel_trained_file_kge_iri :" + cel_trained_file_kge_iri)

    start_module_message = """
        @prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
        @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
        @prefix prov:   <http://www.w3.org/ns/prov#> .
        @prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
        @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
        [] rdf:type enexa:ModuleInstance ;
        enexa:experiment <{}> ;
        alg:instanceOf <http://w3id.org/dice-research/enexa/module/cel-deploy/1.0.0> ;
        <http://w3id.org/dice-research/enexa/module/cel-deploy/parameter/kg> <{}>;
        <http://w3id.org/dice-research/enexa/module/cel-deploy/parameter/kge> <{}>;
        <http://w3id.org/dice-research/enexa/module/cel-deploy/parameter/heuristics> <{}>.
        """.format(experiment_resource, owl_file_iri, embedding_csv_iri, cel_trained_file_kge_iri)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def perform_cel(data, label, url, headers, label_dict):
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_data = response.json()
    # Print response data
    return cel_response_to_markdown(response_data, label_dict)


def cel_response_to_markdown(response_data, label_dict):
    output = ""
    for rated_ce in response_data["prediction"]:
        rated_ce[0] = create_pretty_ce(rated_ce[0], label_dict)

    df = pandas.DataFrame(data=response_data["prediction"], columns=("Class Expression", "F1-Score"))

    # Display the table using tabulate
    table_text = tabulate(df, headers='keys', tablefmt='grid', showindex=False)

    return table_text

def create_pretty_ce(class_expression, label_dict):
    # Handle unicode characters
    # class_expression = class_expression.encode('latin-1').decode('unicode_escape')
    # Find and replace any Q expression (This is soooo ineffective... I hope nobody ever sees it :D
    # If you see it, please improve it! Please!!!)
    classes = re.findall("Q[0-9]+\\b", class_expression)
    # Start replacing the entity IDs with the longest IDs
    classes.sort(key=lambda s: -len(s))
    for c in classes:
        if c in label_dict:
            class_expression = class_expression.replace(c, label_dict.get(c) + " (" + c + ")")
        else:
            print("Unknown entity ID: " + c)
    return class_expression


######## Steps

## upload file ---------------------------------------------------------------------------------------------------------

@app.callback([
    Output('btn-start-extraction-1', "disabled", allow_duplicate=True),
    Output('lbl-upload-status', "children", allow_duplicate=True),
    Output('state-uploadedFile', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')],
    prevent_initial_call=True
)
def file_uploaded(contents, filename):
    if contents is None:
        return True, "there is error", {}
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
            # TODO: add file name
            uploaded_filename = filename  # str(uuid.uuid4())
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
                return False, "ready", {'content': uploaded_file_content, 'experiment_resource': experiment_resource,
                                        'urls_to_process_iri': urls_to_process_iri,
                                        'generation_parameters_IRI': generation_parameters_IRI}


## start extraction ----------------------------------------------------------------------------------------------------

@app.callback(
    [Output('lbl-extraction-status', 'children'),
     Output('state-extraction', 'data', allow_duplicate=True),
     Output('btn-start-extraction-1', 'disabled', allow_duplicate=True),
     Output('interval-component-extraction','disabled',allow_duplicate=True)],
    [Input('btn-start-extraction-1', 'n_clicks'), Input('state-uploadedFile', 'data')],
    prevent_initial_call=True
)
def start_extraction_step(n_clicks, data):
    print("dataXX")
    print(n_clicks)
    print(data)
    if (n_clicks == 1):
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

            print('done!')
            return "extraction done", {'experiment_resource': experiment_resource,
                                              'module_instance_iri': module_instance_iri,'container_id':container_id}, True, False

    else:
        raise PreventUpdate


## extraction log ------------------------------------------------------------------------------------------------
@callback(
    [Output('btn-start-repair-2', "disabled", allow_duplicate=True),
        Output('interval-component-extraction', 'disabled', allow_duplicate=True),
     Output('extraction_docker_log', 'value', allow_duplicate=True),
     Output('extraction_afterrun_state', 'data')],
    [Input('state-extraction', 'data'),
     Input('interval-component-extraction', 'n_intervals'),
     Input('interval-component-extraction', 'disabled')],
    prevent_initial_call=True
)
def extraction_docker_log(data, n_intervals, disabled):
    if (disabled == False):
        container_id = data['container_id']
        module_instance_iri = data['module_instance_iri']
        experiment_resource = data['experiment_resource']
        returnlines = read_container_logs(container_id)
        print('log size is ' + str(len(returnlines)))
        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                               module_instance_iri,
                                                               experiment_resource)
        print('response_check_module_instance_status' + response_check_module_instance_status.text)
        if ("exited" in response_check_module_instance_status.text):

            # todo check if it was successful
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

            return (False, True, '\n'.join(returnlines), {'extracted_file_iri': extracted_file_iri,'experiment_resource':experiment_resource})
        else:
            return (True, False, '\n'.join(returnlines), {})
    else:
        raise PreventUpdate


## start repair ----------------------------------------------------------------------------------------------------
@app.callback(
    [Output('btn-start-tentris-3', "disabled", allow_duplicate=True),
     Output('lbl-repair-status', 'children'),
     Output('state-repair', 'data'),
     Output('btn-start-repair-2', 'disabled', allow_duplicate=True)],
    [Input('btn-start-repair-2', 'n_clicks'), Input('extraction_afterrun_state', 'data')],
    prevent_initial_call=True
)
def start_repair_step(n_clicks, data):
    if (n_clicks == 1):
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

                # changedlines = print_container_logs(container_id_fixing_module)

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

                return False, "done", {'experiment_resource': experiment_resource,
                                       'repaired_a_box_iri': repaired_a_box_iri}, True

            # start_tentris(experiment_resource, repaired_a_box_iri)
    else:
        raise PreventUpdate


## start tentris ----------------------------------------------------------------------------------------------------
@callback(
    [Output('interval-component-tentris', 'disabled', allow_duplicate=True),
     Output('state-tentris', 'data', allow_duplicate=True),
     Output('btn-start-tentris-3', 'disabled'),
     Output('lbl-tentris-status', 'children')],
    [Input('btn-start-tentris-3', 'n_clicks'),
     Input('state-repair', 'data')],
    prevent_initial_call=True
)
def start_tentris_step(n_clicks, data):
    if (n_clicks == 1):
        experiment_resource = data['experiment_resource']
        print(experiment_resource)
        repaired_a_box_iri = data['repaired_a_box_iri']
        print(repaired_a_box_iri)

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
            return False, {'experiment_resource': experiment_resource,
                           'container_id_tentris_step_deployed': container_id_tentris_step_deployed,
                           'tentris_experiment_resource': tentris_experiment_resource,
                           'tentris_relative_file_location_inside_enexa_dir': tentris_relative_file_location_inside_enexa_dir,
                           'container_name_tentris_step_deployed': container_name_tentris_step_deployed}, True, "Done"

    else:
        raise PreventUpdate


## start tentris log ---------------------------------------------------------------------------------------------------
@callback(
    [Output('interval-component-tentris', 'disabled', allow_duplicate=True),
     Output('tentris_docker_log', 'value', allow_duplicate=True),
     Output('btn-start-filter-5m', 'disabled', allow_duplicate=True)],
    [Input('state-tentris', 'data'),
     Input('interval-component-tentris', 'n_intervals'),
     Input('interval-component-tentris', 'disabled')],
    prevent_initial_call=True
)
def tentris_docker_log(data, n_intervals, disabled):
    if (disabled == False):
        container_id_tentris_step_deployed = data['container_id_tentris_step_deployed']
        [returnlines, is_finished] = read_container_logs_stop_when_reach_x(container_id_tentris_step_deployed,
                                                                           "0.0.0.0:9080")
        if (is_finished):
            return True, '\n'.join(returnlines), False
        else:
            return False, '\n'.join(returnlines), True
    else:
        raise PreventUpdate


## start tentris filter ------------------------------------------------------------------------------------------------
@callback(
    [Output('btn-start-cel-transform', 'disabled', allow_duplicate=True),
     Output('lbl-tentris-filter-status', 'children'),
     Output('state-tentris-filter', 'data', allow_duplicate=True),
     Output('btn-start-filter-5m', 'disabled', allow_duplicate=True)],
    [Input('btn-start-filter-5m', 'n_clicks'), Input('state-tentris', 'data')],
    prevent_initial_call=True
)
def start_tentris_filter_step(n_clicks, data):
    if (n_clicks == 1):
        print('start filtering')
        container_name_tentris_step_deployed = data['container_name_tentris_step_deployed']
        tentris_experiment_resource = data['tentris_experiment_resource']
        tentris_relative_file_location_inside_enexa_dir = data['tentris_relative_file_location_inside_enexa_dir']
        triple_store_endpoint = "http://" + container_name_tentris_step_deployed + ":9080/sparql"
        print('triple_store_endpoint is :' + triple_store_endpoint)
        # BASF, Adidas, BOSCH, Tommy Hilfiger, Dickies, Globus, Tesco, Lacoste, Foot Locker, Bohemia Interactive
        all_iri = ["https://www.wikidata.org/wiki/Q9401", "https://www.wikidata.org/wiki/Q3895",
                   "https://www.wikidata.org/wiki/Q234021", "https://www.wikidata.org/wiki/Q634881",
                   "https://www.wikidata.org/wiki/Q114913", "https://www.wikidata.org/wiki/Q457503",
                   "https://www.wikidata.org/wiki/Q487494", "https://www.wikidata.org/wiki/Q309031",
                   "https://www.wikidata.org/wiki/Q63335", "https://www.wikidata.org/wiki/Q890779"]

        # query_str_first = "CONSTRUCT {    ?s ?p ?o .} WHERE {    VALUES ?s { "+all_iri+" }    ?s ?p ?o .}"
        subject_graph = Graph()
        for iri in all_iri:
            query_str_first = "SELECT ?p ?o WHERE {  <" + iri + "> ?p ?o .} "
            print("first query " + query_str_first)
            # st.info("query is : " + query_str_first + " sending to Tentris")
            subject_graph += run_query_triplestore_subject(query_str_first, triple_store_endpoint, iri)

        object_graph = Graph()
        for iri in all_iri:
            query_str_second = "SELECT ?s ?p WHERE {  ?s ?p <" + iri + "> .}"
            print("second query " + query_str_second)
            # st.info("query is : " + query_str_second+ " sending to Tentris")
            object_graph += run_query_triplestore_object(query_str_second, triple_store_endpoint, iri)

        subject_graph += object_graph

        num_triples = len(subject_graph)
        print("concat the graphs the graph size is " + str(num_triples))

        filtered_wikidata5m_file_name = str(uuid.uuid4()) + ".nt"
        filtered_wikidata5m_file_path = ENEXA_SHARED_DIRECTORY + "/" + filtered_wikidata5m_file_name
        # st.info("graph will be save here : "+filtered_wikidata5m_file_path)
        # Serialize the RDF graph as an .nt file

        subject_graph.serialize(destination=filtered_wikidata5m_file_path, format="nt")
        # with open(filtered_wikidata5m_file_path, 'wb') as f:
        #     f.write(firstpartGraph.serialize(format='nt'))
        # #save as file
        # st.success("file saved")

        # f = open(filtered_wikidata5m_file_path , 'w')
        # f.write(firstpart)
        # f.write(secondpart)
        # f.close()
        # add to service
        responce_add_filteredwikidata5m = add_module_configuration_to_enexa_service(
            tentris_experiment_resource,
            tentris_relative_file_location_inside_enexa_dir,
            filtered_wikidata5m_file_name,
            label_for_addition="Adding generated Wikidata5M subset file")
        if (responce_add_filteredwikidata5m.status_code != 200):
            logging.error("cannot add file: " + filtered_wikidata5m_file_path)
        else:
            logging.info("graph add to service ")

            wikidata5m_iri = extract_id_from_turtle(responce_add_filteredwikidata5m.text)

            return False, "done", {'wikidata5m_iri': wikidata5m_iri}, True
    else:
        raise PreventUpdate


## start cel transform ------------------------------------------------------------------------------------------------
@callback(
    [Output('btn-start-cel', 'disabled', allow_duplicate=True),
     Output('lbl-cel-transform-status', 'children'),
     Output('state-cel-transform', 'data', allow_duplicate=True),
     Output('btn-start-cel-transform', 'disabled', allow_duplicate=True)],
    [Input('btn-start-cel-transform', 'n_clicks'), Input('state-tentris-filter', 'data'),
     Input('state-repair', 'data')],
    prevent_initial_call=True
)
def start_cel_transform_step(n_clicks, data_tentris_filter, data_state_repair):
    if n_clicks == 1:
        experiment_resource = data_state_repair['experiment_resource']
        repaired_a_box_iri = data_state_repair['repaired_a_box_iri']
        wikidata5m_iri = data_tentris_filter['wikidata5m_iri']
        print(
            'start cel transform experiment_resource is :' + experiment_resource + ' repaired_a_box_iri :' + repaired_a_box_iri + ' wikidata5m_iri:' + wikidata5m_iri)

        cel_transform_experiment_data = create_experiment_data()
        cel_transform_experiment_resource = cel_transform_experiment_data["experiment_iri"]
        cel_transform_experiment_directory = cel_transform_experiment_data["experiment_folder"]
        cel_transform_relative_file_location_inside_enexa_dir = cel_transform_experiment_directory

        response_transform_step = start_cel_transform_module(experiment_resource, repaired_a_box_iri, wikidata5m_iri)
        # st.info(str(response_transform_step.status_code))
        if (response_transform_step.status_code != 200):
            logging.error("error in running cel transform module")
        else:
            # st.info(" start cel transform strp")
            cel_transform_step_module_instance_iri = extract_id_from_turtle(response_transform_step.text)
            # st.info(" cel_transform_step_module_instance_iri " + cel_transform_step_module_instance_iri)

            if cel_transform_step_module_instance_iri:
                print("id:", cel_transform_step_module_instance_iri)
            else:
                print("No id found in JSON-LD")
                logging.error("No iri for the last module found")
            # st.info("cel_transform_step_module_instance_iri is :" + cel_transform_step_module_instance_iri)
            # st.info("experiment_resource is :" + experiment_resource)

            # st.success("get status experiment_resource is : "+experiment_resource)
            response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                   cel_transform_step_module_instance_iri,
                                                                   experiment_resource)
            print("status is : " + response_check_module_instance_status.text)
            # st.info("response_check_module_instance_status code" + str(response_check_module_instance_status.status_code))

            # Store the text of the info box in the session state
            # st.session_state["info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
            # st.info(st.session_state["info_box_text"])

            # ask for status of the module instance until it is finished
            elapsedTime = SLEEP_IN_SECONDS
            while "exited" not in response_check_module_instance_status.text:
                response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                       cel_transform_step_module_instance_iri,
                                                                       experiment_resource)
                print("status is : " + response_check_module_instance_status.text)
                time.sleep(SLEEP_IN_SECONDS)
                elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                # Update the text of the info box in the session state
                # st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

            # TODO SHOULD NOT BE HARDCODED
            owl_file_iri = extract_output_from_triplestore(META_DATA_ENDPOINT,
                                                           META_DATA_GRAPH_NAME,
                                                           cel_transform_step_module_instance_iri)
            return False, "done", {'experiment_resource': experiment_resource, 'owl_file_iri': owl_file_iri}, True
    else:
        raise PreventUpdate


## start cel step ------------------------------------------------------------------------------------------------
@callback(
    [Output('interval-component-cel', 'disabled', allow_duplicate=True),
     Output('state-cel', 'data', allow_duplicate=True),
     Output('btn-start-cel', 'disabled', allow_duplicate=True)],
    [Input('btn-start-cel', 'n_clicks'), Input('state-cel-transform', 'data')],
    prevent_initial_call=True
)
def start_cel_step(n_clicks, data):
    if n_clicks == 1:
        experiment_resource = data['experiment_resource']
        owl_file_iri = data['owl_file_iri']

        print("Starting class expression learning ... experiment_resource : " + str(
            experiment_resource) + " owl_file_iri: " + str(owl_file_iri))

        cel_experiment_data = create_experiment_data()

        cel_experiment_resource = cel_experiment_data["experiment_iri"]
        cel_experiment_directory = cel_experiment_data["experiment_folder"]
        cel_relative_file_location_inside_enexa_dir = cel_experiment_directory
        # add ontology
        # embedding_csv_iri = extract_embeddings_csv_from_triplestore(META_DATA_ENDPOINT, META_DATA_GRAPH_NAME,experiment_resource)

        # add embedding_csv_iri
        add_preproccessed_embedding_csv = add_module_configuration_to_enexa_service(
            cel_experiment_resource,
            cel_relative_file_location_inside_enexa_dir,
            "Keci_entity_embeddings.csv",
            label_for_addition="Adding Keci embedding model")
        if (add_preproccessed_embedding_csv.status_code != 200):
            logging.error("cannot add file")
        else:
            # st.info("Keci_entity_embeddings file add to servcie" + add_preproccessed_embedding_csv.text + " ")

            embedding_csv_iri = extract_id_from_turtle(add_preproccessed_embedding_csv.text)
            # st.info("starting CEL training module ...")
            response_cel_step = start_cel_module(experiment_resource, owl_file_iri, embedding_csv_iri)
            if (response_cel_step.status_code != 200):
                logging.error("error in running transform module")
            else:
                cel_step_module_instance_iri = extract_id_from_turtle(response_cel_step.text)
                if cel_step_module_instance_iri:
                    print("id:", cel_step_module_instance_iri)
                else:
                    print("No id found in JSON-LD")
                    logging.error("No iri for the last module found")

                container_id_cel_step = extract_X_from_turtle(response_cel_step.text,
                                                              "http://w3id.org/dice-research/enexa/ontology#containerId")
                # st.info("container_id_embeddings_step is : " + container_id_cel_step)
                return False, {'container_id_cel_step': container_id_cel_step,
                               'cel_step_module_instance_iri': cel_step_module_instance_iri,
                               'experiment_resource': experiment_resource, 'embedding_csv_iri': embedding_csv_iri}, True

    else:
        raise PreventUpdate


## start cel log ------------------------------------------------------------------------------------------------
@callback(
    [Output('interval-component-cel', 'disabled', allow_duplicate=True),
     Output('cel_docker_log', 'value', allow_duplicate=True),
     Output('cel_afterrun_state', 'data'),
     Output('btn-start-cel-server', 'disabled', allow_duplicate=True)],
    [Input('state-cel', 'data'),
     Input('interval-component-cel', 'n_intervals'),
     Input('interval-component-cel', 'disabled')],
    prevent_initial_call=True
)
def cel_docker_log(data, n_intervals, disabled):
    if (disabled == False):
        container_id_cel_step = data['container_id_cel_step']
        cel_step_module_instance_iri = data['cel_step_module_instance_iri']
        experiment_resource = data['experiment_resource']
        returnlines = read_container_logs(container_id_cel_step)
        print('log size is ' + str(len(returnlines)))
        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                               cel_step_module_instance_iri,
                                                               experiment_resource)
        print('response_check_module_instance_status' + response_check_module_instance_status.text)
        if ("exited" in response_check_module_instance_status.text):
            cel_trained_file_kge_iri = extract_cel_trained_kge_from_triplestore(META_DATA_ENDPOINT,
                                                                                META_DATA_GRAPH_NAME,
                                                                                cel_step_module_instance_iri)
            return (True, '\n'.join(returnlines), {'cel_trained_file_kge_iri': cel_trained_file_kge_iri}, False)
        else:
            return (False, '\n'.join(returnlines), {}, True)
    else:
        raise PreventUpdate


## serve cel----------------------------------------------------------------------------------------------------
@callback(
    [Output('interval-component-cel-serve', 'disabled', allow_duplicate=True),
     Output('state-cel', 'data', allow_duplicate=True),
     Output('btn-start-cel-server', 'disabled', allow_duplicate=True)],
    [Input('btn-start-cel-server', 'n_clicks'),
     Input('state-cel-transform', 'data'),
     Input('state-cel', 'data'),
     Input('cel_afterrun_state', 'data')],
    prevent_initial_call=True
)
def serve_cel(n_clicks, data_cel_transform, data_cel, data_cel_afterrun_state):
    if n_clicks == 1:
        experiment_resource = data_cel['experiment_resource']
        owl_file_iri = data_cel_transform['owl_file_iri']
        embedding_csv_iri = data_cel['embedding_csv_iri']
        cel_trained_file_kge_iri = data_cel_afterrun_state['cel_trained_file_kge_iri']

        cel_service_experiment_data = create_experiment_data()
        cel_service_experiment_resource = cel_service_experiment_data["experiment_iri"]
        cel_service_experiment_directory = cel_service_experiment_data["experiment_folder"]
        cel_service_relative_file_location_inside_enexa_dir = cel_service_experiment_directory

        response_cel_step_deployed = start_cel_service_module(experiment_resource, owl_file_iri, embedding_csv_iri,
                                                              cel_trained_file_kge_iri)
        container_id_cel_step_deployed = extract_X_from_turtle(response_cel_step_deployed.text,
                                                               "http://w3id.org/dice-research/enexa/ontology#containerId")

        container_name_cel_step_deployed = extract_X_from_turtle(response_cel_step_deployed.text,
                                                                 "http://w3id.org/dice-research/enexa/ontology#containerName")

        cel_deployed_module_instance_iri = extract_id_from_turtle(response_cel_step_deployed.text)
        return False, {'container_id_cel_step_deployed': container_id_cel_step_deployed,
                       'container_name_cel_step_deployed': container_name_cel_step_deployed,
                       'cel_deployed_module_instance_iri': cel_deployed_module_instance_iri,
                       'experiment_resource': experiment_resource}, True

    else:
        raise PreventUpdate


## start cel service log ----------------------------------------------------------------------------------------------
@callback(
    [
        Output('interval-component-cel-serve', 'disabled', allow_duplicate=True),
        Output('cel_serve_docker_log', 'value', allow_duplicate=True),
        Output('btn_cel_example_1', 'disabled', allow_duplicate=True),
        Output('btn_cel_example_2', 'disabled', allow_duplicate=True),
        Output('btn_cel_example_3', 'disabled', allow_duplicate=True),
        Output('btn_cel_example_4', 'disabled', allow_duplicate=True),
    ],
    [Input('state-cel', 'data'),
     Input('interval-component-cel-serve', 'n_intervals'),
     Input('interval-component-cel-serve', 'disabled')
     ],
    prevent_initial_call=True
)
def cel_docker_log_serv(data, n_intervals, disabled):
    if (disabled == False):
        container_id_cel_step_deployed = data['container_id_cel_step_deployed']
        cel_deployed_module_instance_iri = data['cel_deployed_module_instance_iri']
        experiment_resource = data['experiment_resource']
        [returnlines, is_finished] = read_container_logs_stop_when_reach_x(container_id_cel_step_deployed,
                                                                           " * Restarting with stat")
        if is_finished:
            return True, '\n'.join(returnlines), False, False, False, False
        else:
            return False, '\n'.join(returnlines), True, True, True, True
    else:
        raise PreventUpdate


## send Example 1
def get_Example_headers():
    return {
        "Content-Type": "application/json"
    }


def get_Example_label_dict():
    return {
        "Q778575": "conglomerate",
        "Q4830453": "business",
        "Q207652": "chemical industry",
        "Q134161": "joint-stock company",
        "Q270791": "state-owned enterprise",
        "Q249556": "railway company",
        "Q206361": "concern",
        "Q279014": "Societas Europaea",
        "Q726870": "brick and mortar",
        "Q658255": "subsidiary",
        "Q1589009": "privately held company",
        "Q114913": "Dickies",
        "Q507619": "retail chain",
        "Q487494": "Tesco",
        "Q891723": "public company",
        "Q210167": "video game developer",
        "Q180846": "supermarket", }


@callback(Output('txt_result_example_1', 'value'),
          [Input('state-cel', 'data'),
           Input('btn_cel_example_1', 'n_clicks')])
def send_example(data, n_clicks):
    if(n_clicks>0):
        container_name_cel_step_deployed = data['container_name_cel_step_deployed']
        url = "http://" + container_name_cel_step_deployed + ":7860/predict"

        headers = get_Example_headers()

        label_dict = get_Example_label_dict()

        # First example: BASF, Adidas vs. Bosch
        data = {

            "positives": ["https://www.wikidata.org/wiki/Q9401", "https://www.wikidata.org/wiki/Q3895"],
            "negatives": ["https://www.wikidata.org/wiki/Q234021"]

        }
        return perform_cel(data, "$E^+=\\Big\{$BASF (Q9401), Adidas (Q3895)$\\Big\}, E^-=\\Big\{$Bosch (Q234021)$\\Big\}$", url,
                    headers, label_dict)
    else:
        raise PreventUpdate

@callback(Output('txt_result_example_2', 'value'),
              [Input('state-cel', 'data'),
               Input('btn_cel_example_2', 'n_clicks')])
def send_example(data, n_clicks):
        if (n_clicks > 0):
            container_name_cel_step_deployed = data['container_name_cel_step_deployed']
            url = "http://" + container_name_cel_step_deployed + ":7860/predict"

            headers = get_Example_headers()

            label_dict = get_Example_label_dict()

            # Second example: Tommy Hilfiger, Dickies, Globus vs. Tesco, BASF, Adidas
            data = {
                "positives": ["https://www.wikidata.org/wiki/Q634881", "https://www.wikidata.org/wiki/Q114913",
                              "https://www.wikidata.org/wiki/Q457503"],
                "negatives": ["https://www.wikidata.org/wiki/Q487494", "https://www.wikidata.org/wiki/Q9401",
                              "https://www.wikidata.org/wiki/Q3895"]
            }
            return perform_cel(data,
                        "$E^+=\\Big\{$Tommy Hilfiger (Q634881), Dickies (Q114913), Globus (Q457503)$\\Big\}, E^-=\\Big\{$Tesco (Q487494), BASF (Q9401), Adidas (Q3895)$\\Big\}$",
                        url, headers, label_dict)
        else:
            raise PreventUpdate

@callback(Output('txt_result_example_3', 'value'),
              [Input('state-cel', 'data'),
               Input('btn_cel_example_3', 'n_clicks')])
def send_example(data, n_clicks):
        if (n_clicks > 0):
            container_name_cel_step_deployed = data['container_name_cel_step_deployed']
            url = "http://" + container_name_cel_step_deployed + ":7860/predict"

            headers = get_Example_headers()

            label_dict = get_Example_label_dict()

            # Third example: Tommy Hilfiger vs. Dickies, Globus
            data = {
            "positives": ["https://www.wikidata.org/wiki/Q634881"],
            "negatives": ["https://www.wikidata.org/wiki/Q114913", "https://www.wikidata.org/wiki/Q457503"]
            }
            return perform_cel(data,
                "$E^+=\\Big\{$Tommy Hilfiger (Q634881)$\\Big\}, E^-=\\Big\{$Dickies (Q114913), Globus (Q457503)$\\Big\}$",
                url, headers, label_dict)
        else:
            raise PreventUpdate

@callback(Output('txt_result_example_4', 'value'),
              [Input('state-cel', 'data'),
               Input('btn_cel_example_4', 'n_clicks')])
def send_example(data, n_clicks):
        if (n_clicks > 0):
            container_name_cel_step_deployed = data['container_name_cel_step_deployed']
            url = "http://" + container_name_cel_step_deployed + ":7860/predict"

            headers = get_Example_headers()

            label_dict = get_Example_label_dict()
            # Fourth example: Tommy Hilfiger, Dickies vs. Globus, Tesco,
            data = {
                "positives": ["https://www.wikidata.org/wiki/Q634881", "https://www.wikidata.org/wiki/Q114913"],
                "negatives": ["https://www.wikidata.org/wiki/Q457503", "https://www.wikidata.org/wiki/Q487494",
                      "https://www.wikidata.org/wiki/Q63335", "https://www.wikidata.org/wiki/Q309031"]
                }
            return perform_cel(data,
                "$E^+=\\Big\{$Globus (Q457503), Dickies (Q114913)$\\Big\}, E^-=\\Big\{$Tommy Hilfiger (Q634881), Tesco (Q487494), Foot Locker (Q63335), Lacoste (Q309031)$\\Big\}$",
                url, headers, label_dict)
        else:
            raise PreventUpdate


# ## level 1
# @app.callback(
#     Output("btn-start-repair-2", "disabled", allow_duplicate=True),
#     Output("level1", "children"),
#     Input("lbl-extraction-status", "n_clicks"),
#     prevent_initial_call=True
# )
# def update_buttons(button_1_clicks):
#     if button_1_clicks == 1:
#         return False, "First button clicked. Second button is now active."
#     else :
#         raise PreventUpdate


## level 2  ###########################################################################################################


## level 3  ###########################################################################################################


## level 4  ###########################################################################################################

@callback(
     Output('levelIndicator', 'children'),
     Input('submit-val', 'n_clicks'),
     State('input-on-submit', 'value'),
     prevent_initial_call=True
 )
def update_output(n_clicks, value):
    return value

#
#
# @callback(
# [Output('btn-start-extraction-1', "disabled", allow_duplicate=True),
#     Output('btn-start-repair-2', "disabled", allow_duplicate=True),
#      Output('lbl-extraction-status', 'children',allow_duplicate=True),
#     Output('state-extraction', 'data',allow_duplicate=True)],
#     [Input('btn-skip-extraction','n_clicks')],
#     prevent_initial_call=True
# )
# def skipEx(n_clicks):
#     if(n_clicks == 1):
#         return True, False,'skipped', {'experiment_resource':'http://example.org/enexa/6c8231ba-6129-459a-9989-fa3d2f4530cb','extracted_file_iri':'http://example.org/enexa/db37f350-aeeb-49e3-ae19-3c75d94b2349'}
#     else :
#         raise PreventUpdate
#
#
# @callback(
# [Output('label-test-docker', 'children',allow_duplicate=True),
#     Output('interval-component-tentris','disabled',allow_duplicate=True),
#     Output('state-tentris','data',allow_duplicate=True)],
#     [Input('btn-test-docker-log', 'n_clicks')],
#     prevent_initial_call=True
# )
# def test_docker_log(n_clicks):
#     if (n_clicks == 1):
#         experiment_resource = 'http://example.org/enexa/6c8231ba-6129-459a-9989-fa3d2f4530cb'
#         repaired_a_box_iri = 'http://example.org/enexa/1fada534-be3e-4176-8b62-1a62e0d24c59'
#
#         tentris_experiment_data = create_experiment_data()
#         tentris_experiment_resource = tentris_experiment_data["experiment_iri"]
#         tentris_experiment_directory = tentris_experiment_data["experiment_folder"]
#         tentris_relative_file_location_inside_enexa_dir = tentris_experiment_directory
#
#         # add wikidata5m
#         responce_add_wikidata5m = add_module_configuration_to_enexa_service(
#             tentris_experiment_resource,
#             tentris_relative_file_location_inside_enexa_dir,
#             DATASET_NAME_TENTRIS,
#             label_for_addition="Adding Wikidata5M dataset file")
#         if (responce_add_wikidata5m.status_code != 200):
#             logging.error("cannot add file: " + DATASET_NAME_TENTRIS)
#         else:
#             # st.info("data set add to service " + responce_add_wikidata5m.text + " ")
#
#             wikidata5m_unfiltered_iri = extract_id_from_turtle(responce_add_wikidata5m.text)
#
#             response_tentris_step = start_tentris_module(experiment_resource, wikidata5m_unfiltered_iri)
#
#             container_id_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
#                                                                        "http://w3id.org/dice-research/enexa/ontology#containerId")
#
#             container_name_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
#                                                                          "http://w3id.org/dice-research/enexa/ontology#containerName")
#             return "running", False, {'experiment_resource':experiment_resource , 'container_id_tentris_step_deployed':container_id_tentris_step_deployed,'container_name_tentris_step_deployed':container_name_tentris_step_deployed }
#     else :
#         return "nothing", True, {}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=True)
