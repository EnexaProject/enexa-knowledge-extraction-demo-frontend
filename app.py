import json

import streamlit as st
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.processor import SPARQLResult
from streamlit.components.v1 import html

from PIL import Image
import logging
import requests
import pprint
import os
import pprint
import time
import shutil
import docker
import uuid

from decouple import config
from rdflib import Graph
from SPARQLWrapper import SPARQLWrapper

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

# config
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


def write_file_to_folder(folder, filename, content):
    try:
        print("write_file_to_folder to : " + str(folder))
        print ("write_file_to_folder start copy uploaded " + str(filename))

        folder = folder.replace("enexa-dir://", ENEXA_SHARED_DIRECTORY + "/")
        print ("write_file_to_folder folder is : " + str(folder) + " filename is :" + filename)
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

    with st.expander("Now, the ENEXA task will be started CEL service."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


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

    with st.expander("Now, the ENEXA task will be started cel module."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


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

    with st.expander("Now, the ENEXA task will be started cel transform."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

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

    with st.expander("Now, the ENEXA task will be started cel transform."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module

def start_embedding_transform_module(experiment_resource, module_instance_id, ontologyIRI, wikidata5mIRI):
    print("start_embedding_transform_module")
    print("experiment_resource : " + experiment_resource)
    print("module_instance_id : " + module_instance_id)
    print("ontologyIRI : " + ontologyIRI)
    print("wikidata5mIRI : " + wikidata5mIRI)

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

    with st.expander("Now, the ENEXA task will be started embedding transfer."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_embeddings_module(experiment_resource, module_instance_id):
    print("start_embeddings_module")
    print("experiment_resource : " + experiment_resource)
    print("module_instance_id : " + module_instance_id)
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
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/batch_size> {};
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/embedding_dim> {};
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/model> <http://w3id.org/dice-research/enexa/module/dice-embeddings/algorithm/DistMult>;
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/num_epochs> {};
<http://w3id.org/dice-research/enexa/module/dice-embeddings/parameter/path_single_kg> <{}>.
""".format(experiment_resource, EMBEDDINGS_BATCH_SIZE, EMBEDDINGS_DIM, EMBEDDINGS_EPOCH_NUM, module_instance_id)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    with st.expander("Now, the ENEXA task will be started embedding."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_preprocess_module(experiment_resource, iri_to_process):
    print("start_preprocess_module")
    print("experiment_resource : " + experiment_resource)
    print("iri_to_process : " + iri_to_process)
    start_module_message = """
@prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
alg:instanceOf <http://w3id.org/dice-research/enexa/module/wikidata-preproc/1.0.0> ;
<http://w3id.org/dice-research/enexa/module/wikidata-preproc/parameter/input> <{}>.
""".format(experiment_resource, iri_to_process)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    with st.expander("Now, the ENEXA task will be started embedding."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


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

    with st.expander("Now, the ENEXA task will be started kg fixing."):
        st.code(start_module_message, language="turtle")
        st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


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


def extract_X_from_turtle(turtle_text, x):
    print("turtle_text is :"+str(turtle_text))
    print("x is :"+str(x))
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    query = "SELECT ?id ?o \n WHERE { \n ?id <" + x + "> ?o .\n }"
    st.info(query)
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


def extract_X_from_triplestore(X, triple_store_endpoint, graph_name, module_instance_iri):
    print("extract_X_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <" + X + "> ?iri. } }"
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
            "}><" + X + ">").format(
            module_instance_iri)
    else:
        return returnIRI

def run_query_triplestore_subject(query_str, triple_store_endpoint,s):
    g = Graph()
    # st.info("triple store endpoint is :"+triple_store_endpoint)
    sparql = SPARQLWrapper(triple_store_endpoint)
    print("query is :"+query_str)
    print ("endpoint is :"+triple_store_endpoint)
    # st.info(query_str)
    sparql.setQuery(query_str)

    #query_obj = prepareQuery(query_str)
    #st.info(str(query_obj))
    #result = SPARQLResult(triple_store_endpoint, query_obj)
    #g += result
    # Use the query() method to execute the query against the endpoint
    #result = g.query(query_obj, initBindings={'triple_store_endpoint': triple_store_endpoint})

    # Set the result format to JSON
    sparql.setReturnFormat('json')

    # Execute the query and parse the results
    results = sparql.query().convert()

    # Loop through the results and add them to the graph
    #for row in results:
    #    g.add(row)

    #st.success("graph size is : " + str(len(g)))
    #return g

    for result in results["results"]["bindings"]:
        subject = result["s"]["value"]
        predicate = result["p"]["value"]
        oobject = result["o"]["value"]
        g.add((subject, predicate, oobject))

    num_triples = len(g)

    st.success("graph size is : " + str(num_triples))
    return g


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
        st.error(
            "there is no iri in the triple store for <" + module_instance_iri + "><http://w3id.org/dice-research/enexa/module/transform/result/output>")
    else:
        return returnIRI


def extract_embeddings_csv_from_triplestore(triple_store_endpoint, graph_name, experiment_iri):
    print("extract_embeddings_csv_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri ?moduleiri\n WHERE {\n GRAPH <" + graph_name + "> {\n ?moduleiri <http://w3id.org/dice-research/enexa/module/dice-embeddings/result/entity_embeddings.csv> ?iri. \n ?moduleiri <http://w3id.org/dice-research/enexa/ontology#experiment> <" + experiment_iri + ">; } }"
    print(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()
    returnIRI = ""
    for result in results["results"]["bindings"]:
        returnIRI = result["iri"]["value"]

    if returnIRI == None:
        st.error(
            "there is no iri in the triple store for <?moduleiri> <http://w3id.org/dice-research/enexa/module/dice-embeddings/result/entity_embeddings.csv> ?iri; \n <?moduleiri> <http://w3id.org/dice-research/enexa/ontology#experiment> <" + experiment_iri + ">")
    elif returnIRI == None:
        st.error(
            "there is no iri in the triple store for <?moduleiri> <http://w3id.org/dice-research/enexa/module/dice-embeddings/result/entity_embeddings.csv> ?iri; \n <?moduleiri> <http://w3id.org/dice-research/enexa/ontology#experiment> <" + experiment_iri + ">")
    else:
        return returnIRI


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
        st.error(
            "there is no iri in the triple store for <{"
            "}><http://w3id.org/dice-research/enexa/module/transform/result/output>").format(
            module_instance_iri)
    else:
        return returnIRI


def add_file_from_share_folder(experiment_resource,uploaded_filename):
    print("add_module_configuration_to_enexa_service")
    # copy the file in share directory
    print("experiment_resource: " + experiment_resource)
    print("uploaded_filename: " + uploaded_filename)

    # add resource
    ttl_for_registering_the_file_upload = """
        @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
        @prefix prov:   <http://www.w3.org/ns/prov#> .

        [] a prov:Entity ; 
            enexa:experiment <{}> ; 
            enexa:location "{}" .
        """.format(experiment_resource, uploaded_filename)

    ttl_for_registering_the_file_upload_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_file_upload)

    with st.expander("Show message for registering the file upload"):
        st.code(ttl_for_registering_the_file_upload, language="turtle")
        st.code(ttl_for_registering_the_file_upload_as_jsonld, language="json")

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld,
                             headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    print("file added and the response is :" + str(response))
    return response

def add_module_configuration_to_enexa_service(experiment_resource, relative_file_location_inside_enexa_dir,
                                              uploaded_filename):
    print("add_module_configuration_to_enexa_service")
    # copy the file in share directory
    print("experiment_resource: " + experiment_resource)
    print("relative_file_location_inside_enexa_dir: " + relative_file_location_inside_enexa_dir)
    print("uploaded_filename: " + uploaded_filename)

    # if path is not there create it
    path_to_check = ENEXA_SHARED_DIRECTORY + "/" + experiment_resource.replace("http://", "").replace(
        "enexa-dir://", "")
    print("check this path " + path_to_check)
    if not os.path.exists(path_to_check):
        os.makedirs(path_to_check)
    shutil.copyfile(ENEXA_SHARED_DIRECTORY + "/" + uploaded_filename,
                    ENEXA_SHARED_DIRECTORY + "/" + experiment_resource.replace("http://", "").replace(
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


def start_cel_service_step(experiment_resource, owl_file_iri, embedding_csv_iri, cel_trained_file_kge_iri):
    st.info(
        "starting cel service" + "experiment_resource :" + experiment_resource + "owl_file_iri :" + owl_file_iri + "embedding_csv_iri :" + embedding_csv_iri + "cel_trained_file_kge_iri:" + cel_trained_file_kge_iri)
    print(
            "starting cel service" + "experiment_resource :" + experiment_resource + "owl_file_iri :" + owl_file_iri + "embedding_csv_iri :" + embedding_csv_iri + "cel_trained_file_kge_iri:" + cel_trained_file_kge_iri)
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

    # cel_deployed_module_instance_iri = extract_id_from_turtle(response_cel_step_deployed.text)

    read_container_logs_stop_when_reach_x(container_id_cel_step_deployed, " * Restarting with stat")

    # TODO send request here
    url = "http://" + container_name_cel_step_deployed + ":7860/predict"

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "positives": ["https://www.wikidata.org/wiki/Q9401", "https://www.wikidata.org/wiki/Q152051"],
        "negatives": ["https://www.wikidata.org/wiki/Q3895", "https://www.wikidata.org/wiki/Q234021", "https://www.wikidata.org/wiki/Q659379"]
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    # Print the response
    print(response.status_code)
    print(response.text)

    st.info(response.status_code)
    st.info(response.text)


def start_cel_step(experiment_resource, owl_file_iri):
    st.info("starting cel step")
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
        "Keci_entity_embeddings.csv")
    if (add_preproccessed_embedding_csv.status_code != 200):
        st.error("cannot add file")
    else:
        st.info("Keci_entity_embeddings file add " + add_preproccessed_embedding_csv.text + " ")

        embedding_csv_iri = extract_id_from_turtle(add_preproccessed_embedding_csv.text)
        response_cel_step = start_cel_module(experiment_resource, owl_file_iri, embedding_csv_iri)
        if (response_cel_step.status_code != 200):
            st.error("error in running transform module")
        else:
            cel_step_module_instance_iri = extract_id_from_turtle(response_cel_step.text)
            if cel_step_module_instance_iri:
                print("id:", cel_step_module_instance_iri)
            else:
                print("No id found in JSON-LD")
                st.error("No iri for the last module found")
            st.info("cel_step_module_instance_iri is :" + cel_step_module_instance_iri)
            st.info("experiment_resource is :" + experiment_resource)

            container_id_cel_step = extract_X_from_turtle(response_cel_step.text,
                                                          "http://w3id.org/dice-research/enexa/ontology#containerId")
            st.info("container_id_embeddings_step is : " + container_id_cel_step)
            print_container_logs(container_id_cel_step)

            cel_trained_file_kge_iri = extract_cel_trained_kge_from_triplestore(META_DATA_ENDPOINT,
                                                                                META_DATA_GRAPH_NAME,
                                                                                cel_step_module_instance_iri)

            start_cel_service_step(experiment_resource, owl_file_iri, embedding_csv_iri, cel_trained_file_kge_iri)

def start_cel_transform_step(experiment_resource, repaired_abox_iri, wikidata5m_iri):
    # transform nt file to owl
    st.info("starting cel transform step")
    cel_transform_experiment_data = create_experiment_data()
    cel_transform_experiment_resource = cel_transform_experiment_data["experiment_iri"]
    cel_transform_experiment_directory = cel_transform_experiment_data["experiment_folder"]
    cel_transform_relative_file_location_inside_enexa_dir = cel_transform_experiment_directory

    #add reduced kg as owl file w5M-rdf-1.owl
    # st.info("use w5M-rdf-1.owl as kg file")
    # # add wikidata5m
    # responce_add_reduced_owl_file = add_module_configuration_to_enexa_service(
    #     cel_transform_experiment_resource,
    #     cel_transform_relative_file_location_inside_enexa_dir,
    #     "w5M-rdf-1.owl")
    # if (responce_add_reduced_owl_file.status_code != 200):
    #     st.error("cannot add file: " + DATASET_NAME)
    # else:
    #     st.info("file add " + responce_add_reduced_owl_file.text + " ")
    #
    #     owl_file_iri = extract_id_from_turtle(responce_add_reduced_owl_file.text)
    #     start_cel_step(experiment_resource, owl_file_iri)


    # add wikidata5m
    #responce_add_wikidata5m = add_module_configuration_to_enexa_service(
    #    cel_transform_experiment_resource,
    #    cel_transform_relative_file_location_inside_enexa_dir,
    #    DATASET_NAME)
    #if (responce_add_wikidata5m.status_code != 200):
    #    st.error("cannot add file: " + DATASET_NAME)
    #else:
    #    st.info("file add " + responce_add_wikidata5m.text + " ")

    #    wikidata5m_iri = extract_id_from_turtle(responce_add_wikidata5m.text)
    response_transform_step = start_cel_transform_module(experiment_resource, repaired_abox_iri, wikidata5m_iri)
    if (response_transform_step.status_code != 200):
        st.error("error in running cel transform module")
    else:
        cel_transform_step_module_instance_iri = extract_id_from_turtle(response_transform_step.text)
        if cel_transform_step_module_instance_iri:
            print("id:", cel_transform_step_module_instance_iri)
        else:
            print("No id found in JSON-LD")
            st.error("No iri for the last module found")
        st.info("cel_transform_step_module_instance_iri is :" + cel_transform_step_module_instance_iri)
        st.info("experiment_resource is :" + experiment_resource)

        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                               cel_transform_step_module_instance_iri,
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
                                                                   cel_transform_step_module_instance_iri,
                                                                   experiment_resource)
            time.sleep(SLEEP_IN_SECONDS)
            elapsedTime = elapsedTime + SLEEP_IN_SECONDS
            # Update the text of the info box in the session state
            st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

        # TODO SHOULD NOT BE HARDCODED
        owl_file_iri = extract_output_from_triplestore(META_DATA_ENDPOINT,
                                                       META_DATA_GRAPH_NAME,
                                                       cel_transform_step_module_instance_iri)
        start_cel_step(experiment_resource, owl_file_iri)

def start_tentris(experiment_resource, repaired_a_box_iri):
    st.info("starting Tentris step")
    tentris_experiment_data = create_experiment_data()
    tentris_experiment_resource = tentris_experiment_data["experiment_iri"]
    tentris_experiment_directory = tentris_experiment_data["experiment_folder"]
    tentris_relative_file_location_inside_enexa_dir = tentris_experiment_directory

    #add wikidata5m
    responce_add_wikidata5m = add_module_configuration_to_enexa_service(
        tentris_experiment_resource,
        tentris_relative_file_location_inside_enexa_dir,
        DATASET_NAME_TENTRIS)
    if (responce_add_wikidata5m.status_code != 200):
        st.error("cannot add file: " + DATASET_NAME_TENTRIS)
    else:
        st.info("file add " + responce_add_wikidata5m.text + " ")


        wikidata5m_unfiltered_iri = extract_id_from_turtle(responce_add_wikidata5m.text)

        response_tentris_step = start_tentris_module(experiment_resource, wikidata5m_unfiltered_iri)

        container_id_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
                                                               "http://w3id.org/dice-research/enexa/ontology#containerId")


        container_name_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
                                                                 "http://w3id.org/dice-research/enexa/ontology#containerName")


        read_container_logs_stop_when_reach_x(container_id_tentris_step_deployed, "0.0.0.0:9080")

        triple_store_endpoint = "http://" + container_name_tentris_step_deployed + ":9080/sparql"

        all_iri = str("<https://www.wikidata.org/wiki/Q9401> <https://www.wikidata.org/wiki/Q152051> <https://www.wikidata.org/wiki/Q3895> <https://www.wikidata.org/wiki/Q234021> <https://www.wikidata.org/wiki/Q659379>")

        #query_str_first = "CONSTRUCT {    ?s ?p ?o .} WHERE {    VALUES ?s { "+all_iri+" }    ?s ?p ?o .}"
        query_str_first = "SELECT ?p ?o WHERE {  <https://www.wikidata.org/wiki/Q9401> ?p ?o .} "
        print("first query " +query_str_first)
        st.info("first query " +query_str_first)
        firstpartGraph = run_query_triplestore(query_str_first, triple_store_endpoint)

        #query_str_second = "CONSTRUCT {    ?s ?p ?o .} WHERE {    VALUES ?o { "+all_iri+" }    ?s ?p ?o .}"
        query_str_second = "SELECT ?s ?p WHERE {  ?s ?p <https://www.wikidata.org/wiki/Q9401> .}"
        print("second query " + query_str_second)
        st.info("second query " + query_str_second)
        secondpartGraph = run_query_triplestore(query_str_second, triple_store_endpoint)

        firstpartGraph += secondpartGraph
        st.info("concat the graphs")
        filtered_wikidata5m_file_path = ENEXA_SHARED_DIRECTORY + "/" + str(uuid.uuid4())+".nt"
        st.info(filtered_wikidata5m_file_path)
        # Serialize the RDF graph as an .nt file

        firstpartGraph.serialize(destination=filtered_wikidata5m_file_path, format="nt")

        # with open(filtered_wikidata5m_file_path, 'wb') as f:
        #     f.write(firstpartGraph.serialize(format='nt'))
        # #save as file
        # st.success("file saved")

        # f = open(filtered_wikidata5m_file_path , 'w')
        # f.write(firstpart)
        # f.write(secondpart)
        # f.close()
        #add to service
        responce_add_filteredwikidata5m = add_file_from_share_folder(
            tentris_experiment_resource,
            filtered_wikidata5m_file_path)
        if (responce_add_wikidata5m.status_code != 200):
            st.error("cannot add file: " + filtered_wikidata5m_file_path)
        else:
            st.info("file add " + responce_add_wikidata5m.text + " ")
            wikidata5m_iri = extract_id_from_turtle(responce_add_filteredwikidata5m.text)

            start_cel_transform_step(experiment_resource, repaired_a_box_iri, wikidata5m_iri)


# def start_embeddings_step(experiment_resource, iri_nt_file_from_preprocess_embedding):
#     st.info("starting embeding step")
#     embeddings_experiment_data = create_experiment_data()
#     # embeddings_experiment_resource = embeddings_experiment_data["experiment_iri"]
#     embeddings_experiment_directory = embeddings_experiment_data["experiment_folder"]
#     # embeddings_relative_file_location_inside_enexa_dir = embeddings_experiment_directory
#     # add ontology
#     response_embeddings_step = start_embeddings_module(experiment_resource, iri_nt_file_from_preprocess_embedding)
#     if (response_embeddings_step.status_code != 200):
#         st.error("wrror in running transform module")
#     else:
#         embeddings_step_module_instance_iri = extract_id_from_turtle(response_embeddings_step.text)
#         if embeddings_step_module_instance_iri:
#             print("id:", embeddings_step_module_instance_iri)
#         else:
#             print("No id found in JSON-LD")
#             st.error("No iri for the last module found")
#         st.info("embeddings_step_module_instance_iri is :" + embeddings_step_module_instance_iri)
#         st.info("experiment_resource is :" + experiment_resource)
#
#         response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, embeddings_step_module_instance_iri,
#                                                                experiment_resource)
#
#         # st.info("response_check_module_instance_status code" + str(
#         #     response_check_module_instance_status.status_code))
#
#         # Store the text of the info box in the session state
#
#         container_id_embeddings_step = extract_X_from_turtle(response_embeddings_step.text,
#                                                              "http://w3id.org/dice-research/enexa/ontology#containerId")
#         st.info("container_id_embeddings_step is : " + container_id_embeddings_step)
#         print_container_logs(container_id_embeddings_step)
#
#         st.success(
#             "Module instance ({}) for the experiment ({}) finished successfully.".format(
#                 embeddings_step_module_instance_iri,
#                 experiment_resource))
#
#         start_cel_transform_step(experiment_resource, iri_nt_file_from_preprocess_embedding)


# def start_embeddings_transform_step(experiment_resource, iri_from_last_step):
#     st.info("starting transform step")
#     transform_experiment_data = create_experiment_data()
#     transform_experiment_resource = transform_experiment_data["experiment_iri"]
#     transform_experiment_directory = transform_experiment_data["experiment_folder"]
#     transform_relative_file_location_inside_enexa_dir = transform_experiment_directory
#     # add ontology
#     transform_responce_ontology_resource = add_module_configuration_to_enexa_service(
#         transform_experiment_resource,
#         transform_relative_file_location_inside_enexa_dir,
#         "1-ontology_version_1.ttl")
#
#     if (transform_responce_ontology_resource.status_code != 200):
#         st.error("can not add ontology file ")
#     else:
#         # add wikipedia
#         # add ontology
#         wiki_data_5m_resource = add_module_configuration_to_enexa_service(
#             transform_experiment_resource,
#             transform_relative_file_location_inside_enexa_dir,
#             DATASET_NAME)
#         # wiki_data_5m_resource = add_module_configuration_to_enexa_service(
#         #     transform_experiment_resource,
#         #     transform_relative_file_location_inside_enexa_dir,
#         #     "wikidata5M.ttl.gz")
#         if (wiki_data_5m_resource.status_code != 200):
#             st.error(" can not add wikidata5m")
#         else:
#             ontologyIRI = extract_id_from_turtle(transform_responce_ontology_resource.text)
#             wikidata5mIRI = extract_id_from_turtle(wiki_data_5m_resource.text)
#             response_transform_step = start_embedding_transform_module(experiment_resource, iri_from_last_step,
#                                                                        ontologyIRI,
#                                                                        wikidata5mIRI)
#             if (response_transform_step.status_code != 200):
#                 st.error("wrror in running transform module")
#             else:
#                 transform_step_module_instance_iri = extract_id_from_turtle(response_transform_step.text)
#                 if transform_step_module_instance_iri:
#                     print("id:", transform_step_module_instance_iri)
#                 else:
#                     print("No id found in JSON-LD")
#                     st.error("No iri for the last module found")
#                 # st.info("transform_step_module_instance_iri is :" + transform_step_module_instance_iri)
#                 # st.info("experiment_resource is :" + experiment_resource)
#
#                 response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
#                                                                        transform_step_module_instance_iri,
#                                                                        experiment_resource)
#
#                 # st.info("response_check_module_instance_status code" + str(response_check_module_instance_status.status_code))
#
#                 # Store the text of the info box in the session state
#                 # st.session_state[
#                 #     "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
#                 # st.info(st.session_state["info_box_text"])
#
#                 # ask for status of the module instance until it is finished
#                 elapsedTime = SLEEP_IN_SECONDS
#                 while "exited" not in response_check_module_instance_status.text:
#                     response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
#                                                                            transform_step_module_instance_iri,
#                                                                            experiment_resource)
#
#                     time.sleep(SLEEP_IN_SECONDS)
#                     elapsedTime = elapsedTime + SLEEP_IN_SECONDS
#                     # Update the text of the info box in the session state
#                     st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)
#
#                 # st.success(
#                 #     "Module instance ({}) for the experiment ({}) finished successfully.".format(
#                 #         transform_step_module_instance_iri,
#                 #         experiment_resource))
#                 # TODO SHOULD NOT BE HARDCODED
#                 # transformed_file_iri = extract_output_from_triplestore(META_DATA_ENDPOINT,META_DATA_GRAPH_NAME, transform_step_module_instance_iri)
#                 transformed_file_iri = extract_X_from_triplestore(
#                     "http://w3id.org/dice-research/enexa/module/transform/result/output", META_DATA_ENDPOINT,
#                     META_DATA_GRAPH_NAME,
#                     transform_step_module_instance_iri)
#
#                 # start_embedding_data_preprocess(experiment_resource, transformed_file_iri)
#                 start_embeddings_step(experiment_resource, transformed_file_iri)


# def start_embedding_data_preprocess(experiment_resource, not_processed_data_iri):
#     st.info("starting preprocess step" + str(experiment_resource) + " " + str(not_processed_data_iri))
#     embedding_preproc_experiment_data = create_experiment_data()
#     embedding_preproc_experiment_resource = embedding_preproc_experiment_data["experiment_iri"]
#     embedding_preproc_experiment_directory = embedding_preproc_experiment_data["experiment_folder"]
#     embedding_preproc_relative_file_location_inside_enexa_dir = embedding_preproc_experiment_directory
#     responce_embedding_preproc_step = start_preprocess_module(experiment_resource, not_processed_data_iri)
#     if (responce_embedding_preproc_step.status_code != 200):
#         st.error("error in preprocess data")
#     else:
#         embedding_preproc_step_module_instance_iri = extract_id_from_turtle(responce_embedding_preproc_step.text)
#         if embedding_preproc_step_module_instance_iri:
#             print("embedding_preproc_step_module_instance_iri id:", embedding_preproc_step_module_instance_iri)
#         else:
#             print("No id found in embedding_preproc_step_module_instance_iri")
#             st.error("No iri for the embedding_preproc_step_module_instance_iri")
#
#         response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
#                                                                embedding_preproc_step_module_instance_iri,
#                                                                experiment_resource)
#         st.info("response_check_module_instance_status code" + str(
#             response_check_module_instance_status.status_code))
#
#         # Store the text of the info box in the session state
#         st.session_state[
#             "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
#         st.info(st.session_state["info_box_text"])
#
#         # ask for status of the module instance until it is finished
#         elapsedTime = SLEEP_IN_SECONDS
#         while "exited" not in response_check_module_instance_status.text:
#             response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
#                                                                    embedding_preproc_step_module_instance_iri,
#                                                                    experiment_resource)
#             time.sleep(SLEEP_IN_SECONDS)
#             elapsedTime = elapsedTime + SLEEP_IN_SECONDS
#             # Update the text of the info box in the session state
#             st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)
#
#         st.success(
#             "Module instance ({}) for the experiment ({}) finished successfully.".format(
#                 embedding_preproc_step_module_instance_iri,
#                 experiment_resource))
#         # TODO SHOULD NOT BE HARDCODED
#         processed_file_iri = extract_X_from_triplestore(
#             "http://w3id.org/dice-research/enexa/module/wikidata-preproc/result/output", META_DATA_ENDPOINT,
#             META_DATA_GRAPH_NAME,
#             embedding_preproc_step_module_instance_iri)
#
#         start_embeddings_step(experiment_resource, processed_file_iri)
#         # start_embeddings_transform_step(experiment_resource, processed_file_iri)




def start_repair_step(experiment_resource, module_instance_id):
    st.info("starting second step")

    second_step_experiment_data = create_experiment_data()
    second_step_experiment_resource = second_step_experiment_data["experiment_iri"]
    second_step_experiment_directory = second_step_experiment_data["experiment_folder"]
    second_step_relative_file_location_inside_enexa_dir = second_step_experiment_directory
    # second_step_configFile_resource = ""

    # st.info("experiment_resource : " + experiment_resource)
    # st.info("module_instance_id : " + module_instance_id)
    # st.info("second_step_experiment_resource: " + second_step_experiment_resource)
    # st.info("second_step_experiment_directory : " + second_step_experiment_directory)
    # st.info(
    #     "second_step_relative_file_location_inside_enexa_dir : " + second_step_relative_file_location_inside_enexa_dir)

    second_step_responce_configFile_resource = add_module_configuration_to_enexa_service(
        second_step_experiment_resource,
        second_step_relative_file_location_inside_enexa_dir,
        "1-ontology_version_1.ttl")
    if (second_step_responce_configFile_resource.status_code != 200):
        st.error("cannot add file")
    else:
        st.info("file add " + second_step_responce_configFile_resource.text + " ")

        uploadedFileId = extract_id_from_turtle(second_step_responce_configFile_resource.text)

        # st.info("uploadedFileId " + uploadedFileId)

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

            container_id_fixing_module = extract_X_from_turtle(response_second_step.text,
                                                               "http://w3id.org/dice-research/enexa/ontology#containerId")
            st.info("container_id_fixing_module is : " + container_id_fixing_module)
            changedlines = print_container_logs(container_id_fixing_module)
            with st.expander("fixed triples :"):
                for change in changedlines:
                    st.text(change)

            st.success(
                "Module instance ({}) for the experiment ({}) finished successfully.".format(
                    second_step_module_instance_iri,
                    experiment_resource))

            # repaired_A_box_iri = extract_X_from_triplestore("http://w3id.org/dice-research/enexa/module/kg-fixing/result/fixedKG", META_DATA_ENDPOINT,
            #   META_DATA_GRAPH_NAME,
            #  second_step_module_instance_iri)
            # start_embeddings_transform_step(experiment_resource, second_step_module_instance_iri)
            # start_embedding_data_preprocess(experiment_resource, repaired_A_box_iri)

            # skip embeddings
            repaired_a_box_iri = extract_id_from_turtle(response_second_step.text)
            st.info("repaired a box iri os : " + str(repaired_a_box_iri))
            #start_cel_transform_step(experiment_resource, repaired_a_box_iri)
            start_tentris(experiment_resource, repaired_a_box_iri)


def print_container_logs(container_id):
    returnlines = []
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        with st.expander("logs for this container :" + str(container_id)):
            for log_line in container.logs(stream=True):
                if str(log_line.decode("utf-8")).startswith("INFO: ******* Found inconsistency:") or str(
                        log_line.decode("utf-8")).startswith("INFO: ******* Apply Sound fix:"):
                    returnlines.append(log_line.decode("utf-8"))
                st.text(log_line.decode("utf-8"))
    except docker.errors.NotFound:
        st.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        st.error("An error occurred: " + str(e))
    return returnlines


def read_container_logs_stop_when_reach_x(container_id, x):
    st.info("looking for "+x)
    returnlines = []
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        with st.expander("logs for this container :" + str(container_id)):
            for log_line in container.logs(stream=True):
                st.text(log_line)
                if x in str(log_line.decode("utf-8")):
                    return
    except docker.errors.NotFound:
        st.error("Container with ID " + str(container_id) + " not found.")
    except Exception as e:
        st.error("An error occurred: " + str(e))
    return returnlines


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
            generation_parameters_IRI = extract_id_from_turtle(responce_configFile_resource.text)

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

            # st.info("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)
            # st.info("relative_file_location_inside_enexa_dir is :" + relative_file_location_inside_enexa_dir)

            write_file_to_folder(relative_file_location_inside_enexa_dir, uploaded_filename, uploaded_file_content)

            response_adding_uploaded_file = add_resource_to_service(experiment_resource,
                                                                    relative_file_location_inside_enexa_dir,
                                                                    uploaded_filename)
            if response_adding_uploaded_file.status_code != 200:
                st.error("Error while registering ENEXA configuration file upload. :cry:")
                st.error(response_adding_uploaded_file.status_code + " " + str(response_adding_uploaded_file))
            else:
                st.success("File : \"" + uploaded_filename + "\" add to Enexa service successfully :ok_hand:")
                urls_to_process_iri = extract_id_from_turtle(response_adding_uploaded_file.text)

                st.info("the ID for added resource (uploaded file) is: {}".format(urls_to_process_iri))

                # start a module (i.e., a new container instance of the demanded experiment will be started)
                # st.info ("###configFile_resource is :" + str(generation_parameters_IRI))
                st.info(" starting extraction module ...")

                response_start_module = start_extraction_module(experiment_resource, urls_to_process_iri,
                                                                generation_parameters_IRI)
                if response_start_module.status_code != 200:
                    st.error("Error while starting ENEXA task: {}.".format(response_start_module))
                else:
                    st.success("extraction module started")
                    print("starting container")
                    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
                    # st.info("Now, the ENEXA task should be started at the ENEXA platform. Please check the status of your task at the ENEXA platform. Request to {} done.".format(start_container_endpoint))
                    print(str(response_start_module))

                    module_instance_iri = extract_id_from_turtle(response_start_module.text)
                    container_id = extract_X_from_turtle(response_start_module.text,
                                                         "http://w3id.org/dice-research/enexa/ontology#containerId")
                    st.info("container_id is : " + container_id)
                    print_container_logs(container_id)

                    if module_instance_iri:
                        print("id:", module_instance_iri)
                    else:
                        print("No id found in JSON-LD")

                    # st.info("the IRI for extraction module is: {}".format(urls_to_process_iri))

                    # st.info("module_instance_id is :" + module_instance_iri)
                    # st.info("experiment_resource is :" + experiment_resource)

                    # response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, module_instance_iri,
                    #                                                                           experiment_resource)

                    # st.info("response_check_module_instance_status code" + str(
                    #                        response_check_module_instance_status.status_code))

                    ## Store the text of the info box in the session state
                    # st.session_state[
                    #    "info_box_text"] = "response_check_module_instance_status" + response_check_module_instance_status.text
                    ## Create a text element
                    # progress_element_1 = st.empty()
                    # progress_element_1.text("starting module")

                    # # ask for status of the module instance until it is finished
                    # elapsedTime = SLEEP_IN_SECONDS
                    # while "exited" not in response_check_module_instance_status.text:
                    #    response_check_module_instance_status = get_the_status(SERVER_ENDPOINT, module_instance_iri,
                    #                                                           experiment_resource)
                    #
                    # time.sleep(SLEEP_IN_SECONDS)
                    # elapsedTime = elapsedTime + SLEEP_IN_SECONDS
                    # # Update the text of the info box in the session state
                    # progress_element_1.text("Waiting for result ({} sec) ... ".format(elapsedTime))

                    # progress_element_1.text("result is ready . elapsed time is ({} sec) ".format(elapsedTime))
                    st.success(
                        "Module instance ({}) for the experiment ({}) finished successfully.".format(
                            module_instance_iri, experiment_resource))

                    # waiting = True
                    # repair_step_button_pushed = False
                    # if not repair_step_button_pushed:
                    #     if st.button("Start Repair Step"):
                    #         # Call the function with the entered values
                    #         st.info("start repairing step")
                    #         st.markdown("<hr/>", unsafe_allow_html=True)
                    #         repair_step_button_pushed = True
                    #         waiting = False
                    # while waiting:
                    #     time.sleep(1)
                    extracted_file_iri = extract_X_from_triplestore(
                        "http://w3id.org/dice-research/enexa/module/extraction/result/triples", META_DATA_ENDPOINT,
                        META_DATA_GRAPH_NAME,
                        module_instance_iri)
                    start_repair_step(experiment_resource, extracted_file_iri)

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
#
#
# def cel_transform_test():
#     transformed_file_iri = start_cel_transform_step(text_experiment_resource, text_module_instance_iri)
#
#
# st.button('cel_transform_test', on_click=cel_transform_test)
#
# if 'clicked' not in st.session_state:
#     st.session_state.clicked = False
#
#
# def click_button():
#     # start_repair_step("http://example.org/enexa/6b37c04c-1ef5-4a00-a3a2-c7a174ac3d3c", "http://example.org/enexa/ca47579f-bbd2-4ee6-b151-587a251f67c9")
#     start_embeddings_transform_step("http://example.org/enexa/6b37c04c-1ef5-4a00-a3a2-c7a174ac3d3c",
#                          "http://example.org/enexa/29c5dfb1-d857-4082-86e1-cff1bb8785a3")
#     # start_embeddings_step("http://example.org/enexa/6b37c04c-1ef5-4a00-a3a2-c7a174ac3d3c","http://example.org/enexa/7fd0c144-86b9-4bd1-9a8b-e13f415ef0b6")
#
#
# st.button('Click me', on_click=click_button)
#
# def test2():
#     transformed_file_iri = extract_output_from_triplestore(META_DATA_ENDPOINT,
#                                                            META_DATA_GRAPH_NAME,
#                                                            "http://example.org/enexa/e31c63ef-1f13-4bbc-8bcc-505b4930ec6d")
#
# st.button('test2', on_click=test2)
#
#

# text_experiment_resource = st.text_input("experiment_resource", key="experiment_resource")
# text_extracted_file_iri = st.text_input("extracted_file_iri", key="extracted_file_iri")
#
#
# def start_test_repair_step():
#     transformed_file_iri = start_repair_step(text_experiment_resource, text_extracted_file_iri)
#
# st.button('test repair step', on_click=start_test_repair_step)


# def send_cel_req():
#     start_cel_service_step("http://example.org/enexa/1520a653-a0ea-46e9-8e2d-f73feab7a953",
#                            "http://example.org/enexa/40a05d2f-d622-4dc6-8840-4ea45bae4364",
#                            "http://example.org/enexa/c9d46f6c-2261-409d-91cc-4f5b91039710",
#                            "http://example.org/enexa/fdce6926-17cb-44a3-b36c-96fdc88c266c")
#
#
# st.button('send cel request', on_click=send_cel_req)

def send_tentris_req():
    start_tentris("http://example.org/enexa/5dc9e661-6c55-4d52-96e3-96219873d14f",
                           "http://example.org/enexa/76fe2f40-9fe8-4b1a-9e09-d817e6591dc2")


st.button('continue from tentris', on_click=send_tentris_req)
