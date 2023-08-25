import json

import streamlit as st
from streamlit.components.v1 import html

from PIL import Image
import base64
from io import StringIO
import logging
import requests
import pprint
import os
import pprint
import time
import shutil
from rdflib import Graph
from decouple import config
from rdflib import Graph
from SPARQLWrapper import SPARQLWrapper


logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

# config
SERVER_ENDPOINT = config("SERVER_ENDPOINT", default="http://localhost:8080")
print("SERVER_ENDPOINT is :" + SERVER_ENDPOINT)

ENEXA_SHARED_DIRECTORY = config("ENEXA_SHARED_DIRECTORY", default="/home/farshad/test/enexa/shared")
print("ENEXA_SHARED_DIRECTORY is :" + ENEXA_SHARED_DIRECTORY)

ENEXA_WRITEABLE_DIRECTORY = config("ENEXA_WRITEABLE_DIRECTORY", default=ENEXA_SHARED_DIRECTORY + "/experiments")
print("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)

SLEEP_IN_SECONDS = config("SLEEP_IN_SECONDS", default=5, cast=int)
print("SLEEP_IN_SECONDS is :" + str(SLEEP_IN_SECONDS))

# constants
ENEXA_LOGO = "https://raw.githubusercontent.com/EnexaProject/enexaproject.github.io/main/images/enexacontent/enexa_logo_v0.png?raw=true"
ENEXA_EXPERIMENT_SHARED_DIRECTORY_LITERAL = "http://w3id.org/dice-research/enexa/ontology#sharedDirectory"


def write_file_to_folder(folder, filename, content):
    try:
        print(" to : " + str(folder))
        print ("start copy uploaded " + str(filename))

        folder = folder.replace("enexa-dir://", ENEXA_SHARED_DIRECTORY + "/")
        print ("folder is : " + str(folder) + " filename is :" + filename)
        # create directory if not exists
        if not os.path.exists(folder):
            print ("not exist make dir :" + folder)
            os.makedirs(folder)

        with open(folder + "/" + filename, "wb") as f:
            print (" write...")
            f.write(content)
    except Exception as exc:
        print (exc)


st.set_page_config(layout="wide", initial_sidebar_state="expanded",
                   page_title="ENEXA Integration Demo",
                   #    page_icon=Image.open(ENEXA_LOGO)
                   )


def create_experiment_data():
    """
    returns the data of a fresh experiment, with experiment IRI and ...
  """
    response = requests.post(SERVER_ENDPOINT + "/start-experiment", data="")
    if response.status_code == 200 or response.status_code == 201:
        st.code(pprint.pformat(response.json(), indent=2), language="json")
        return {
            "experiment_iri": response.json()["@id"],
            "experiment_folder": response.json()[ENEXA_EXPERIMENT_SHARED_DIRECTORY_LITERAL],
            "raw": response.json()
        }
    else:
        st.error("Error while starting experiment. No experiment IRI received.")
        st.error(response)

    return "http://example.org/experiment1"


def add_resource_to_service(experiment_resource, relative_file_location_inside_enexa_dir, file_to_add):
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

    with st.expander("Show message for registering the file upload"):
        st.code(ttl_for_registering_the_file_upload, language="turtle")
        st.code(ttl_for_registering_the_file_upload_as_jsonld, language="json")

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld,
                             headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    print("file added and the response is :" + str(response))
    return response


def turtle_to_jsonld(turtle_data):
    """
    transforms RDF Turtle data to JSON-LD
  """
    graph = Graph()
    print("turtle file is as : " + str(turtle_data))
    graph.parse(data=turtle_data, format="turtle")
    return graph.serialize(format="json-ld", indent=2)


def start_transform_module(experiment_resource, module_instance_id, ontologyIRI, wikidata5mIRI):
    print(experiment_resource)
    print(module_instance_id)
    print(ontologyIRI)
    print(wikidata5mIRI)

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
<http://w3id.org/dice-research/enexa/module/transform/parameter/input> <{}>;
<http://w3id.org/dice-research/enexa/module/transform/parameter/outputMediaType> <https://www.iana.org/assignments/media-types/application/n-triples>.
""".format(experiment_resource, module_instance_id, ontologyIRI, wikidata5mIRI)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    with st.expander("Now, the ENEXA task will be started kg fixing."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_embeddings_module(experiment_resource, module_instance_id):
    print(experiment_resource)
    print(module_instance_id)
    start_module_message = """
@prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
alg:instanceOf <http://w3id.org/dice-research/enexa/module/dice-embeddings/1.0.0> ;
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/batch_size> 10;
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/embedding_dim> 2;
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/model> <http://w3id.org/dice-research/enexa/module/dice-embeddings/algorithm/DistMult>;
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/num_epochs> 1;
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/path_single_kg> <{}>.
""".format(experiment_resource, module_instance_id)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    with st.expander("Now, the ENEXA task will be started kg fixing."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_kg_fixing_module(experiment_resource, module_instance_id, second_step_responce_configFile_resource):
    print(experiment_resource)
    print(module_instance_id)
    print(second_step_responce_configFile_resource)

    start_module_message = """
@prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
alg:instanceOf <http://w3id.org/dice-research/enexa/module/kg-fixing/1.0.0> ;
<http://w3id.org/dice-research/enexa/module/extraction/parameter/a-boxFile> <{}>;
<http://w3id.org/dice-research/enexa/module/extraction/parameter/t-boxFile> <{}>.
""".format(experiment_resource, module_instance_id, second_step_responce_configFile_resource)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    with st.expander("Now, the ENEXA task will be started kg fixing."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_extraction_module(experiment_resource, configFile_resorce):
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
""".format(experiment_resource, file_id, configFile_resorce)
    print(file_id)
    print(experiment_resource)
    print(start_module_message)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    with st.expander("Now, the ENEXA task will be started at the ENEXA platform using the following message."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def get_module_instance_status_message(experiment_resource, module_instance_iri):
    """
    returns the message for checking the status of the module instance
  """
    check_module_instance_status_message = """
<{}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://w3id.org/dice-research/enexa/ontology#ModuleInstance>;
<http://w3id.org/dice-research/enexa/ontology#experiment> <{}> .
""".format(module_instance_iri, experiment_resource)

    print (check_module_instance_status_message)

    check_module_instance_status_message_as_jsonld = turtle_to_jsonld(check_module_instance_status_message)

    print (check_module_instance_status_message_as_jsonld)

    with st.expander("Check status of the module instance every {} seconds.".format(SLEEP_IN_SECONDS)):
        st.code(check_module_instance_status_message, language="turtle")
        st.code(check_module_instance_status_message_as_jsonld, language="json")

    return check_module_instance_status_message_as_jsonld


def print_banner_to_console():
    with open("images/banner.txt") as file:
        data = file.read()
        print(data)


st.title("ENEXA Integration Demo")

# print_banner_to_console()

st.markdown(
    """
This demo is showing the integration of the processing steps regarding the Class Expression Learning in ENEXA.

## Knowledge Extraction 

### Input: Upload JSON files with URLs for the knowledge extraction

Upload a JSON file containing one array of URLs to Wikipedia articles.

""")
uploaded_files = st.file_uploader("Upload a JSON file", accept_multiple_files=True, label_visibility="collapsed",
                                  type=["json"])
print("uploaded file is :" + str(uploaded_files))


def extract_id_from_turtle(turtle_text):
    print ("input text is :" + turtle_text)
    graph = Graph()
    print ("graph initiated")
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
    print ("query run")
    # Extract and return IDs
    ids = [str(result["id"]) for result in results][0]
    print ("extracted id is : " + ids)
    return ids


def add_module_configuration_to_enexa_service(experiment_resource, relative_file_location_inside_enexa_dir,
                                              uploaded_filename):
    # copy the file in share directory
    # //shutil.copyfile("/home/farshad/test/enexa/generation_parameters.json", "/home/farshad/test/enexa/experiments/generation_parameters.json")
    print(experiment_resource)
    # if path is not there create it
    path_to_check = "/home/farshad/test/enexa/shared/" + experiment_resource.replace("http://", "").replace(
        "enexa-dir://", "")
    print ("check this path " + path_to_check)
    if not os.path.exists(path_to_check):
        os.makedirs(path_to_check)
    shutil.copyfile("/home/farshad/test/enexa/shared/" + uploaded_filename,
                    "/home/farshad/test/enexa/shared/" + experiment_resource.replace("http://", "").replace(
                        "enexa-dir://", "") + "/" + uploaded_filename)
    # add resource
    ttl_for_registering_the_file_upload = """
    @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
    @prefix prov:   <http://www.w3.org/ns/prov#> .

    [] a prov:Entity ; 
        enexa:experiment <{}> ; 
        enexa:location "{}/{}" .
    """.format(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename)

    ttl_for_registering_the_file_upload_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_file_upload)

    with st.expander("Show message for registering the file upload"):
        st.code(ttl_for_registering_the_file_upload, language="turtle")
        st.code(ttl_for_registering_the_file_upload_as_jsonld, language="json")

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld,
                             headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    print("file added and the response is :" + str(response))
    return response


def start_embeddings_step(experiment_resource, iri_from_last_step):
    st.info("starting embeding step")
    embeddings_experiment_data = create_experiment_data()
    embeddings_experiment_resource = embeddings_experiment_data["experiment_iri"]
    embeddings_experiment_directory = embeddings_experiment_data["experiment_folder"]
    embeddings_relative_file_location_inside_enexa_dir = embeddings_experiment_directory
    # add ontology
    response_embeddings_step = start_embeddings_module(experiment_resource, iri_from_last_step)
    if (response_embeddings_step.status_code != 200):
        st.error("wrror in running transform module")
    else:
        embeddings_step_module_instance_iri = extract_id_from_turtle(response_embeddings_step.text)
        if embeddings_step_module_instance_iri:
            print("id:", embeddings_step_module_instance_iri)
        else:
            print("No id found in JSON-LD")
            st.error("No iri for the last module found")
        st.info("embeddings_step_module_instance_iri is :" + embeddings_step_module_instance_iri)
        st.info("experiment_resource is :" + experiment_resource)

        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, embeddings_step_module_instance_iri,
                                                               experiment_resource)

        st.info("response_check_module_instance_status code" + str(
            response_check_module_instance_status.status_code))

        # Store the text of the info box in the session state
        st.session_state[
            "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
        st.info(st.session_state["info_box_text"])

        # ask for status of the module instance until it is finished
        elapsedTime = SLEEP_IN_SECONDS
        while "exited" not in response_check_module_instance_status.text:
            response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                   embeddings_step_module_instance_iri,
                                                                   experiment_resource)
            print(response_check_module_instance_status.text)
            time.sleep(SLEEP_IN_SECONDS)
            elapsedTime = elapsedTime + SLEEP_IN_SECONDS
            # Update the text of the info box in the session state
            st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

        st.success(
            "Module instance ({}) for the experiment ({}) finished successfully.".format(
                embeddings_step_module_instance_iri,
                experiment_resource))

        # start_embedings_step(experiment_resource, transform_step_module_instance_iri)


def extract_output_from_triplestore(triple_store_endpoint, graph_name, module_instance_iri):
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <"+graph_name+"> {\n <"+module_instance_iri+"> <http://w3id.org/dice-research/enexa/module/transform/result/output> ?iri. } }"
    print(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()
    returnIRI = ""
    for result in results["results"]["bindings"]:
        returnIRI = result["iri"]["value"]

    if returnIRI == "":
        st.error(
            "there is no iri in the triple store for <{"
            "}><http://w3id.org/dice-research/enexa/module/transform/result/output>").format(
            module_instance_iri)
    else:
        return returnIRI


def start_transform_step(experiment_resource, iri_from_last_step):
    st.info("starting transform step")
    transform_experiment_data = create_experiment_data()
    transform_experiment_resource = transform_experiment_data["experiment_iri"]
    transform_experiment_directory = transform_experiment_data["experiment_folder"]
    transform_relative_file_location_inside_enexa_dir = transform_experiment_directory
    # add ontology
    transform_responce_ontology_resource = add_module_configuration_to_enexa_service(
        transform_experiment_resource,
        transform_relative_file_location_inside_enexa_dir,
        "1-ontology_version_1.ttl")

    if (transform_responce_ontology_resource.status_code != 200):
        st.error("can not add ontology file ")
    else:
        # add wikipedia
        # add ontology
        wiki_data_5m_resource = add_module_configuration_to_enexa_service(
            transform_experiment_resource,
            transform_relative_file_location_inside_enexa_dir,
            "wikidata5M-short.ttl.gz")
        if (wiki_data_5m_resource.status_code != 200):
            st.error(" can not add wikidata5m")
        else:
            ontologyIRI = extract_id_from_turtle(transform_responce_ontology_resource.text)
            wikidata5mIRI = extract_id_from_turtle(wiki_data_5m_resource.text)
            response_transform_step = start_transform_module(experiment_resource, iri_from_last_step, ontologyIRI,
                                                             wikidata5mIRI)
            if (response_transform_step.status_code != 200):
                st.error("wrror in running transform module")
            else:
                transform_step_module_instance_iri = extract_id_from_turtle(response_transform_step.text)
                if transform_step_module_instance_iri:
                    print("id:", transform_step_module_instance_iri)
                else:
                    print("No id found in JSON-LD")
                    st.error("No iri for the last module found")
                st.info("transform_step_module_instance_iri is :" + transform_step_module_instance_iri)
                st.info("experiment_resource is :" + experiment_resource)

                response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                       transform_step_module_instance_iri,
                                                                       experiment_resource)

                st.info("response_check_module_instance_status code" + str(
                    response_check_module_instance_status.status_code))

                # Store the text of the info box in the session state
                st.session_state[
                    "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
                st.info(st.session_state["info_box_text"])

                # ask for status of the module instance until it is finished
                elapsedTime = SLEEP_IN_SECONDS
                while "exited" not in response_check_module_instance_status.text:
                    response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                                           transform_step_module_instance_iri,
                                                                           experiment_resource)
                    print(response_check_module_instance_status.text)
                    time.sleep(SLEEP_IN_SECONDS)
                    elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                    # Update the text of the info box in the session state
                    st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

                st.success(
                    "Module instance ({}) for the experiment ({}) finished successfully.".format(
                        transform_step_module_instance_iri,
                        experiment_resource))
                #TODO SHOULD NOT BE HARDCODED
                transformed_file_iri = extract_output_from_triplestore("http://localhost:3030/mydataset","http://example.org/meta-data", transform_step_module_instance_iri)

                start_embeddings_step(experiment_resource, transformed_file_iri)


def start_repair_step(experiment_resource, module_instance_id):
    st.info("starting second step")

    second_step_experiment_data = create_experiment_data()
    second_step_experiment_resource = second_step_experiment_data["experiment_iri"]
    second_step_experiment_directory = second_step_experiment_data["experiment_folder"]
    second_step_relative_file_location_inside_enexa_dir = second_step_experiment_directory
    # second_step_configFile_resource = ""

    st.info("experiment_resource : " + experiment_resource)
    st.info("module_instance_id : " + module_instance_id)
    st.info("second_step_experiment_resource: " + second_step_experiment_resource)
    st.info("second_step_experiment_directory : " + second_step_experiment_directory)
    st.info(
        "second_step_relative_file_location_inside_enexa_dir : " + second_step_relative_file_location_inside_enexa_dir)

    second_step_responce_configFile_resource = add_module_configuration_to_enexa_service(
        second_step_experiment_resource,
        second_step_relative_file_location_inside_enexa_dir,
        "1-ontology_version_1.ttl")
    if (second_step_responce_configFile_resource.status_code != 200):
        st.error("cannot add file")
    else:
        st.info("file add " + second_step_responce_configFile_resource.text + " ")

        uploadedFileId = extract_id_from_turtle(second_step_responce_configFile_resource.text)

        st.info("uploadedFileId " + uploadedFileId)

        response_second_step = start_kg_fixing_module(experiment_resource, module_instance_id, uploadedFileId)

        if response_second_step.status_code != 200:
            st.error("Error while starting Knowldge Graph Fixing  task: {}.".format(response_start_module))
        else:
            second_step_module_instance_iri = extract_id_from_turtle(response_second_step.text)
            if second_step_module_instance_iri:
                print("id:", second_step_module_instance_iri)
            else:
                print("No id found in JSON-LD")
            st.info("module_instance_id is :" + second_step_module_instance_iri)
            st.info("experiment_resource is :" + experiment_resource)

            response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, second_step_module_instance_iri,
                                                                   experiment_resource)

            st.info(
                "response_check_module_instance_status code" + str(response_check_module_instance_status.status_code))

            # Store the text of the info box in the session state
            st.session_state[
                "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
            st.info(st.session_state["info_box_text"])

            # ask for status of the module instance until it is finished
            elapsedTime = SLEEP_IN_SECONDS
            while "exited" not in response_check_module_instance_status.text:
                response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, second_step_module_instance_iri,
                                                                       experiment_resource)
                print(response_check_module_instance_status.text)
                time.sleep(SLEEP_IN_SECONDS)
                elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                # Update the text of the info box in the session state
                st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

            st.success(
                "Module instance ({}) for the experiment ({}) finished successfully.".format(
                    second_step_module_instance_iri,
                    experiment_resource))

            start_transform_step(experiment_resource, second_step_module_instance_iri)


def get_the_status(SERVER_ENDPOINT, module_instance_iri, experiment_resource):
    return requests.get(
        SERVER_ENDPOINT + "/container-status?moduleInstanceIRI=" + module_instance_iri + "&experimentIRI=" + experiment_resource)


if uploaded_files is not None and uploaded_files != []:
    for uploaded_file in uploaded_files:

        # create empty experiment instance
        experiment_data = create_experiment_data()
        experiment_resource = experiment_data["experiment_iri"]
        experiment_directory = experiment_data["experiment_folder"]
        st.info("experiment started")
        # TODO
        # relative_file_location_inside_enexa_dir = ENEXA_SHARED_DIRECTORY + "/" + experiment_directory
        relative_file_location_inside_enexa_dir = experiment_directory

        # add resource config file
        # experiment_resource, relative_file_location_inside_enexa_dir,uploaded_filename
        configFile_resource = ""
        responce_configFile_resource = add_module_configuration_to_enexa_service(experiment_resource,
                                                                                 relative_file_location_inside_enexa_dir,
                                                                                 "generation_parameters.json")
        if responce_configFile_resource.status_code != 200:
            st.error("error in upload configuration file ")
        else:
            st.success("ENEXA generation_parameters.json file upload registered successfully.")
            # st.info(responce_configFile_resource.text)
            # configFile_resource = extract_id_from_turtle(responce_configFile_resource.text)
            # st.success("configFile_resource is task: {}".format(configFile_resource))

            uploaded_filename = uploaded_file.name.replace(" ", "_")
            uploaded_file_content = uploaded_file.read()

            # UI file upload
            write_file_to_folder(ENEXA_WRITEABLE_DIRECTORY, uploaded_filename, uploaded_file_content)
            print("File {} uploaded successfully and stored in experiment's directory: {}".format(uploaded_filename,
                                                                                                  ENEXA_WRITEABLE_DIRECTORY))
            st.info("File :\" {} \" uploaded successfully and stored in experiment's directory: \" {} \" ".format(
                uploaded_filename,
                ENEXA_WRITEABLE_DIRECTORY))

            # send configuration file to ENEXA service
            # print ("*****relative_file_location_inside_enexa_dir is :"+relative_file_location_inside_enexa_dir)

            st.info("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)
            st.info("relative_file_location_inside_enexa_dir is :" + relative_file_location_inside_enexa_dir)

            write_file_to_folder(relative_file_location_inside_enexa_dir, uploaded_filename, uploaded_file_content)

            response_adding_uploaded_file = add_resource_to_service(experiment_resource,
                                                                    relative_file_location_inside_enexa_dir,
                                                                    uploaded_filename)
            if response_adding_uploaded_file.status_code != 200:
                st.error("Error while registering ENEXA configuration file upload. :cry:")
                st.error(response_adding_uploaded_file.status_code + " " + str(response_adding_uploaded_file))
            else:
                st.success("File : \" {} \" add to Enexa service successfully :ok_hand:")
                file_id = extract_id_from_turtle(response_adding_uploaded_file.text)

                st.info("the ID for added resource (uploaded file) is: {}".format(file_id))

                # start a module (i.e., a new container instance of the demanded experiment will be started)
                print ("###configFile_resource is :" + str(configFile_resource))
                st.info(" starting extraction module ...")
                response_start_module = start_extraction_module(experiment_resource, configFile_resource)
                if response_start_module.status_code != 200:
                    st.error("Error while starting ENEXA task: {}.".format(response_start_module))
                else:
                    st.success("extraction module started")
                    print("starting container")
                    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
                    # st.info("Now, the ENEXA task should be started at the ENEXA platform. Please check the status of your task at the ENEXA platform. Request to {} done.".format(start_container_endpoint))
                    print(str(response_start_module))

                    module_instance_iri = extract_id_from_turtle(response_start_module.text)

                    if module_instance_iri:
                        print("id:", module_instance_iri)
                    else:
                        print("No id found in JSON-LD")

                    st.info("the IRI for extraction module is: {}".format(file_id))

                    st.info("module_instance_id is :" + module_instance_iri)
                    st.info("experiment_resource is :" + experiment_resource)

                    response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, module_instance_iri,
                                                                           experiment_resource)

                    st.info("response_check_module_instance_status code" + str(
                        response_check_module_instance_status.status_code))

                    # Store the text of the info box in the session state
                    st.session_state[
                        "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
                    st.info(st.session_state["info_box_text"])

                    # ask for status of the module instance until it is finished
                    elapsedTime = SLEEP_IN_SECONDS
                    while "exited" not in response_check_module_instance_status.text:
                        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, module_instance_iri,
                                                                               experiment_resource)
                        print(response_check_module_instance_status.text)
                        time.sleep(SLEEP_IN_SECONDS)
                        elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                        # Update the text of the info box in the session state
                        st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

                    st.success(
                        "Module instance ({}) for the experiment ({}) finished successfully.".format(
                            module_instance_iri, experiment_resource))

                    start_repair_step(experiment_resource, module_instance_iri)

        # st.markdown("#### Upload (preliminary) T-Box data")

# generation_configuration_file= st.file_uploader("Upload a TTL file", type=["ttl"], accept_multiple_files=False, label_visibility="collapsed")

# st.markdown("#### Upload (preliminary) T-Box data")

# st.file_uploader("Upload a TTL file", type=["ttl"], accept_multiple_files=False, label_visibility="collapsed")

# st.markdown("#### Input schema (SPARQL endpoint)")

# input_schema = st.text_input("SPARQL endpoint", help="e.g., http://localhost:3030/ds/query")

# st.markdown("""
# #### SPARQL Queries (JSON-LD)

# Text: 

# ### Output

# **The result will be shown a RDF data file (TTL?).**

# **The result file will be handed to the ENEXA API for further processing.**

# """)

text_experiment_resource = st.text_input("experiment_resource", key="experiment_resource")

text_module_instance_iri = st.text_input("module_instance_iri", key="module_instance_iri")

if 'clicked' not in st.session_state:
    st.session_state.clicked = False


def click_button():
    # start_repair_step("http://example.org/enexa/6b37c04c-1ef5-4a00-a3a2-c7a174ac3d3c", "http://example.org/enexa/ca47579f-bbd2-4ee6-b151-587a251f67c9")
    start_transform_step("http://example.org/enexa/6b37c04c-1ef5-4a00-a3a2-c7a174ac3d3c",
                         "http://example.org/enexa/29c5dfb1-d857-4082-86e1-cff1bb8785a3")
    # start_embeddings_step("http://example.org/enexa/6b37c04c-1ef5-4a00-a3a2-c7a174ac3d3c","http://example.org/enexa/7fd0c144-86b9-4bd1-9a8b-e13f415ef0b6")


st.button('Click me', on_click=click_button)

def test2():
    transformed_file_iri = extract_output_from_triplestore("http://localhost:3030/mydataset",
                                                           "http://example.org/meta-data",
                                                           "http://example.org/enexa/e31c63ef-1f13-4bbc-8bcc-505b4930ec6d")

st.button('test2', on_click=test2)