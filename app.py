import json
import random
import time

import rdflib
import streamlit as st
from rdflib.compat import cast_bytes
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
import re
import pandas as pd

from decouple import config as configD
from rdflib import Graph, URIRef
from SPARQLWrapper import SPARQLWrapper
from kubernetes import client, config

import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

appName = "app3"
sleep_Before_show_explanation_link_in_seconds=35



# config
SERVER_ENDPOINT= configD("SERVER_ENDPOINT", default="http://localhost:8080")
logging.info("SERVER_ENDPOINT is :" + SERVER_ENDPOINT)

META_DATA_ENDPOINT= configD("ENEXA_META_DATA_ENDPOINT", default="http://localhost:3030/mydataset",cast=str)
logging.info("META_DATA_ENDPOINT is : " + META_DATA_ENDPOINT)

ENEXA_SHARED_DIRECTORY = configD("ENEXA_SHARED_DIRECTORY", default="/home/shared",cast=str)
logging.info("ENEXA_SHARED_DIRECTORY is :" + ENEXA_SHARED_DIRECTORY)

META_DATA_GRAPH_NAME = configD("ENEXA_META_DATA_GRAPH", default="http://example.org/meta-data",cast=str)
logging.info("META_DATA_GRAPH_NAME is :" + META_DATA_GRAPH_NAME)

ENEXA_WRITEABLE_DIRECTORY = configD("ENEXA_WRITEABLE_DIRECTORY", default=ENEXA_SHARED_DIRECTORY + "/experiments",cast=str)
logging.info("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)

SLEEP_IN_SECONDS = configD("SLEEP_IN_SECONDS", default=5, cast=int)
logging.info("SLEEP_IN_SECONDS is :" + str(SLEEP_IN_SECONDS))

EMBEDDINGS_BATCH_SIZE = configD("EMBEDDINGS_BATCH_SIZE", default=20, cast=int)
logging.info("EMBEDDINGS_BATCH_SIZE is :" + str(EMBEDDINGS_BATCH_SIZE))

EMBEDDINGS_DIM = configD("EMBEDDINGS_DIM", default=3, cast=int)
logging.info("EMBEDDINGS_DIM is:" + str(EMBEDDINGS_DIM))

EMBEDDINGS_EPOCH_NUM = configD("EMBEDDINGS_EPOCH_NUM", default=1, cast=int)
logging.info("EMBEDDINGS_EPOCH_NUM is :" + str(EMBEDDINGS_EPOCH_NUM))

DATASET_NAME_TENTRIS = configD("DATASET_NAME_TENTRIS")
logging.info("DATASET_NAME is :" + str(DATASET_NAME_TENTRIS))

# constants
ENEXA_LOGO = "https://raw.githubusercontent.com/EnexaProject/enexaproject.github.io/main/images/enexacontent/enexa_logo_v0.png?raw=true"
ENEXA_EXPERIMENT_SHARED_DIRECTORY_LITERAL = "http://w3id.org/dice-research/enexa/ontology#sharedDirectory"

# Streamlit init
st.set_page_config(layout="wide", initial_sidebar_state="expanded",
                   page_title="ENEXA Integration Demo",
                   #    page_icon=Image.open(ENEXA_LOGO)
                   )

WIKIDATA_PATTERN = re.compile("(Q|P)[0-9]+")

def write_file_to_folder(folder, filename, content):
    try:
        logging.info("write_file_to_folder to : " + str(folder))
        logging.info("write_file_to_folder start copy uploaded " + str(filename))

        folder = folder.replace("enexa-dir://", ENEXA_SHARED_DIRECTORY + "/")
        logging.info("write_file_to_folder folder is : " + str(folder) + " filename is :" + filename)
        # create directory if not exists
        if not os.path.exists(folder):
            logging.info("not exist make dir :" + folder)
            os.makedirs(folder)

        if isinstance(content, str):
            with open(folder + "/" + filename, "w") as f:
                f.write(content)
        elif isinstance(content, bytes):
            with open(folder + "/" + filename, "wb") as f:
                f.write(content)
        else:
            st.error(" unknown content")
    except Exception as exc:
        st.error(exc)
        logging.info(exc)



def create_experiment_data():
    """
    returns the data of a fresh experiment, with experiment IRI and ...
  """
    response = requests.post(SERVER_ENDPOINT + "/start-experiment", data="",
                             headers={"Content-Type": "application/ld+json", "Accept": "application/ld+json"})
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


def add_resource_to_service(experiment_resource, relative_file_location_inside_enexa_dir, file_to_add,
                            label_for_addition="File added"):
    #st.info("send uploaded file to enexa service ")
    #st.info("experiment_resource is :" + experiment_resource)
    #st.info("relative_file_location_inside_enexa_dir is :" + relative_file_location_inside_enexa_dir)
    #st.info("uploaded_filename is :" + file_to_add)
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
    logging.info("file added and the response is :" + str(response))
    return response


def turtle_to_jsonld(turtle_data):
    """
    transforms RDF Turtle data to JSON-LD
  """
    graph = Graph()
    logging.info("turtle file is as : " + str(turtle_data))
    graph.parse(data=turtle_data, format="turtle")
    return graph.serialize(format="json-ld", indent=2)


def start_cel_service_module(experiment_resource, triplestoreIRI):
    logging.info("start_cel_service_module")
    logging.info("experiment_resource : " + experiment_resource)
    logging.info("triplestoreIRI : " + triplestoreIRI)

    start_module_message = """
        @prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
        @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
        @prefix prov:   <http://www.w3.org/ns/prov#> .
        @prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
        @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
        [] rdf:type enexa:ModuleInstance ;
        enexa:experiment <{}> ;
        alg:instanceOf <http://w3id.org/dice-research/enexa/module/cel-deploy/1.3.0> ;
        <http://w3id.org/dice-research/enexa/module/cel-deploy/parameter/endpoint> <{}> .
        """.format(experiment_resource, triplestoreIRI)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    # with st.expander("▶️ Querying the ENEXA service to start the CEL-deploy module."):
    #     st.code(start_module_message, language="turtle")
    #     st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def deprecate_start_cel_module(experiment_resource, owl_file_iri, embedding_csv_iri):
    logging.info("start_cel_module")
    logging.info("experiment_resource: " + str(experiment_resource))
    logging.info("owl_file_iri : " + str(owl_file_iri))
    logging.info("embedding_csv_iri : " + str(embedding_csv_iri))

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

    # with st.expander("▶️ Querying the ENEXA service to start the CEL-training module."):
    #     st.code(start_module_message, language="turtle")
    #     st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_cel_transform_module(experiment_resource, nt_file_iri, second_input):
    logging.info("start_cel_transform_module")
    logging.info("experiment_resource : " + experiment_resource)
    logging.info("nt_file_iri : " + nt_file_iri)

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

    # with st.expander("▶️ Querying the ENEXA service to start the transformation module."):
    #     st.code(start_module_message, language="turtle")
    #     st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})

    # st.info("responce is "+ response_start_module.text )
    # st.info("responce status is "+ str(response_start_module.status_code))
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
    alg:instanceOf <http://w3id.org/dice-research/enexa/module/tentris/0.3.0-SNAPSHOT-1> ;
    <http://w3id.org/dice-research/enexa/module/tentris/parameter/file> <{}>.
    """.format(experiment_resource, wikidata5m_unfiltered_iri)

    start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

    # with st.expander("▶️ Querying the ENEXA service to start the Tentris module"):
    #     st.code(start_module_message, language="turtle")
    #     st.code(start_module_message_as_jsonld, language="json")

    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
    response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld,
                                          headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    return response_start_module


def start_explanation_module(experiment_resource, json_object, chatbot_label):
    json_string = json.dumps(json_object)
    # add json file
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    random_filename = ''.join(random.choice(chars) for i in range(16))

    explanation_step_experiment_data = experiment_data  # create_experiment_data()
    explanation_experiment_directory = explanation_step_experiment_data["experiment_folder"]

    file_name = random_filename + ".json"
    #st.info(json_string)

    write_file_to_folder("enexa-dir://explanationfiles", file_name, json_string)

    # # Use tempfile.NamedTemporaryFile to create a temporary file with a random name
    # with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
    #     filename = temp_file.name
    #     # Write the JSON data to the file
    #     json.dump(json.loads(json_string), temp_file)

    response_adding_explanation_file = add_resource_to_service(experiment_resource,
                                                               "enexa-dir://explanationfiles",
                                                               file_name,
                                                               label_for_addition="Adding file explanation json")
    if response_adding_explanation_file.status_code != 200:
        st.error("Error while registering exmplanation json file. :cry:")
        st.error(response_adding_explanation_file.status_code + " " + str(response_adding_explanation_file))
    else:
        # st.success("File : \"" + uploaded_filename + "\" add to Enexa service successfully :ok_hand:")
        urls_to_explanation_json_iri = extract_id_from_turtle(response_adding_explanation_file.text)

        # start module
        # return the name for url

        response_add_openapi_key = add_resource_to_service(experiment_resource,
                                                                   "enexa-dir://explanationfiles",
                                                                   "openapi.key",
                                                                   label_for_addition="Adding file explanation json")

        if (response_add_openapi_key.status_code != 200):
            st.error("cannot add file")
        else:

            urls_to_openai_key_iri = extract_id_from_turtle(response_add_openapi_key.text)


            start_module_message = """
            @prefix alg: <http://www.w3id.org/dice-research/ontologies/algorithm/2023/06/> .
            @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
            @prefix prov:   <http://www.w3.org/ns/prov#> .
            @prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
            @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            [] rdf:type enexa:ModuleInstance ;
            enexa:experiment <{}> ;
            alg:instanceOf <http://w3id.org/dice-research/enexa/module/explanation/0.1.0> ;
            <http://w3id.org/dice-research/enexa/module/explanation/parameter/path_json> <{}>;
            <http://w3id.org/dice-research/enexa/module/explanation/parameter/path_to_key_file> <{}> .
            """.format(experiment_resource, urls_to_explanation_json_iri, urls_to_openai_key_iri)

            start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)



            # with st.expander("▶️ Querying the ENEXA service to start the Explanation module"):
            #     st.code(start_module_message, language="turtle")
            #     st.code(start_module_message_as_jsonld, language="json")

            start_container_endpoint = SERVER_ENDPOINT + "/start-container"
            response_start_module_explain = requests.post(start_container_endpoint, data=start_module_message_as_jsonld, headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
            container_name_explain = extract_X_from_turtle(response_start_module_explain.text,
                                                           "http://w3id.org/dice-research/enexa/ontology#containerName")
            url_expl_service = "http://enexa-demo.cs.uni-paderborn.de/"+container_name_explain+"/"

            #st.info(f'Loading explanation module for {chatbot_label} , please wait ...')
            time.sleep(sleep_Before_show_explanation_link_in_seconds)

            #st.markdown('[Explanation chatbot for {chatbot_label}]('+url_expl_service+')')
            st.markdown(f'[Explanation chatbot for {chatbot_label}]({url_expl_service})')
            return response_start_module_explain


def start_embedding_transform_module(experiment_resource, module_instance_id, ontologyIRI, wikidata5mIRI):
    logging.info("start_embedding_transform_module")
    logging.info("experiment_resource : " + experiment_resource)
    logging.info("module_instance_id : " + module_instance_id)
    logging.info("ontologyIRI : " + ontologyIRI)
    logging.info("wikidata5mIRI : " + wikidata5mIRI)

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
    logging.info("start_embeddings_module")
    logging.info("experiment_resource : " + experiment_resource)
    logging.info("module_instance_id : " + module_instance_id)
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
    logging.info("start_preprocess_module")
    logging.info("experiment_resource : " + experiment_resource)
    logging.info("iri_to_process : " + iri_to_process)
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
    logging.info("start_kg_fixing_module")
    logging.info("experiment_resource :" + experiment_resource)
    logging.info("module_instance_id :" + module_instance_id)
    logging.info("second_step_responce_configFile_resource :" + second_step_responce_configFile_resource)

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

    logging.info(check_module_instance_status_message)

    check_module_instance_status_message_as_jsonld = turtle_to_jsonld(check_module_instance_status_message)

    logging.info(check_module_instance_status_message_as_jsonld)

    with st.expander("Check status of the module instance every {} seconds.".format(SLEEP_IN_SECONDS)):
        st.code(check_module_instance_status_message, language="turtle")
        st.code(check_module_instance_status_message_as_jsonld, language="json")

    return check_module_instance_status_message_as_jsonld


def print_banner_to_console():
    with open("images/banner.txt") as file:
        data = file.read()
        logging.info(data)


st.title("ENEXA Integration Demo")

##opening the image
image = Image.open('images/Enexa-Demo-May-24.png')
##displaying the image on streamlit app
st.image(image)  # , caption='Enter any caption here'

# print_banner_to_console()

st.markdown(
    """ 
Input: Upload JSON files containing an array of URLs to Wikipedia articles URLs for the knowledge extraction.
""")
uploaded_files = st.file_uploader("Upload a JSON file", accept_multiple_files=True, label_visibility="collapsed",
                                  type=["json"])
logging.info("uploaded file is :" + str(uploaded_files))


def extract_X_from_turtle(turtle_text, x):
    logging.info("----------extract_X_from_turtle-------------")
    logging.info("turtle_text is :" + str(turtle_text))
    logging.info("x is :" + str(x))
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    query = "SELECT ?id ?o \n WHERE { \n ?id <" + x + "> ?o .\n }"
    st.info(query)
    # Execute the query
    results = graph.query(query)
    # Extract and return IDs
    st.json(results)
    o = [str(result["o"]) for result in results][0]
    logging.info("extracted X is : " + o)
    return o


def extract_id_from_turtle(turtle_text):
    logging.info("extract_id_from_turtle input text is :" + turtle_text)
    graph = Graph()
    # Parse the Turtle file
    graph.parse(data=turtle_text, format="ttl")
    logging.info("graph parsed")
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
    logging.info("extracted id is : " + ids)
    return ids


def extract_X_from_triplestore(X, triple_store_endpoint, graph_name, module_instance_iri):
    st.info("debug: running this query X is "+str(X)+" triple_store_endpoint is : "+str(triple_store_endpoint)+" graph_name is : "+str(graph_name)+" module_instance_iri is : "+str(module_instance_iri))
    logging.info("extract_X_from_triplestore"+str(module_instance_iri))
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + str(graph_name) + "> {\n <" + str(module_instance_iri) + "> <" + X + "> ?iri. } }"
    st.info("debug: query is :"+query_str)
    logging.info(query_str)
    sparql.setQuery(query_str)
    sparql.setReturnFormat('json')
    results = sparql.query().convert()
    st.json(results)
    returnIRI = ""
    for result in results["results"]["bindings"]:
        returnIRI = result["iri"]["value"]

    if returnIRI == "":
        st.error("there is no iri in the triple store for <"+str(module_instance_iri)+"><" + X + ">")
    else:
        st.info("debug: returnIRI is"+str(returnIRI))
        return returnIRI


def run_query_triplestore_subject(query_str, triple_store_endpoint, s):
    g = Graph()
    # st.info("triple store endpoint is :"+triple_store_endpoint)
    sparql = SPARQLWrapper(triple_store_endpoint)
    logging.info("query is :" + query_str)
    logging.info("endpoint is :" + triple_store_endpoint)
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
    logging.info("query is :" + query_str)
    logging.info("endpoint is :" + triple_store_endpoint)
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


def extract_output_from_triplestore(triple_store_endpoint, graph_name, module_instance_iri):
    logging.info("extract_output_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <http://w3id.org/dice-research/enexa/module/transform/result/output> ?iri. } }"
    logging.info(query_str)
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
    logging.info("extract_embeddings_csv_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri ?moduleiri\n WHERE {\n GRAPH <" + graph_name + "> {\n ?moduleiri <http://w3id.org/dice-research/enexa/module/dice-embeddings/result/entity_embeddings.csv> ?iri. \n ?moduleiri <http://w3id.org/dice-research/enexa/ontology#experiment> <" + experiment_iri + ">; } }"
    logging.info(query_str)
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
    logging.info("extract_cel_trained_kge_from_triplestore")
    g = Graph()
    sparql = SPARQLWrapper(triple_store_endpoint)
    query_str = " SELECT ?iri \n WHERE {\n GRAPH <" + graph_name + "> {\n <" + module_instance_iri + "> <http://w3id.org/dice-research/enexa/module/cel-train/result/heuristics> ?iri. } }"
    logging.info(query_str)
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


def add_tentris_endpoint_to_metadata(experiment_resource, tentris_endpoint):
    st.info("add tentris endpoint to triplestore : " + tentris_endpoint)

    # Split the experimentIRI using "/"
    path_elements = experiment_resource.split("/")

    # Get the last element of the split path
    experimentIRI = path_elements[-1]
    logging.info("experimentIRI is : " + experimentIRI)
    # add resource
    ttl_for_registering_the_tentris_endpoint = """
    @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
    @prefix prov:   <http://www.w3.org/ns/prov#> .

    [] a prov:Entity ; 
        enexa:experiment <{}> ; 
        <http://w3id.org/dice-research/enexa/module/cel-deploy/parameter/endpoint> "{}" .
    """.format(experiment_resource, tentris_endpoint)

    ttl_for_registering_the_tentris_endpoint_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_tentris_endpoint)

    with st.expander("➕ "):
        st.code(ttl_for_registering_the_tentris_endpoint, language="turtle")
        st.code(ttl_for_registering_the_tentris_endpoint_as_jsonld, language="json")

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_tentris_endpoint_as_jsonld,
                             headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    st.info("endpoint added :" + str(response))
    return response


def add_module_configuration_to_enexa_service(experiment_resource, relative_file_location_inside_enexa_dir,
                                              uploaded_filename, label_for_addition="File added"):
    #st.info("start add configuration ")
    #st.info("add_module_configuration_to_enexa_service")
    # copy the file in share directory
    #st.info("experiment_resource: " + experiment_resource)
    #st.info("relative_file_location_inside_enexa_dir: " + relative_file_location_inside_enexa_dir)
    #st.info("uploaded_filename: " + uploaded_filename)

    # Split the experimentIRI using "/"
    path_elements = experiment_resource.split("/")

    # Get the last element of the split path
    experimentIRI = path_elements[-1]
    logging.info("experimentIRI is : " + experimentIRI)

    # if path is not there create it
    path_to_check = os.path.join(ENEXA_SHARED_DIRECTORY, appName, experimentIRI)

    #st.info("check this path " + path_to_check)
    if not os.path.exists(path_to_check):
        #st.info("make path")
        os.makedirs(path_to_check)
    #st.info("copy from " + os.path.join(ENEXA_SHARED_DIRECTORY, uploaded_filename) + " to " + os.path.join( ENEXA_SHARED_DIRECTORY, appName, experimentIRI, uploaded_filename))
    #st.info("start copy")
    # shutil.copyfile(os.path.join(ENEXA_SHARED_DIRECTORY, uploaded_filename),
    #                 os.path.join(ENEXA_SHARED_DIRECTORY, appName, experimentIRI, uploaded_filename))

    # Define paths
    source_path = os.path.join(ENEXA_SHARED_DIRECTORY, uploaded_filename)
    destination_path = os.path.join(ENEXA_SHARED_DIRECTORY, appName, experimentIRI, uploaded_filename)

    # Try to copy the file and check if it was successful
    try:
        shutil.copyfile(source_path, destination_path)
        #st.info(f"File copied successfully from {source_path} to {destination_path}")
    except shutil.SameFileError:
        st.error("Source and destination represents the same file.")
    except IsADirectoryError:
        st.error("Destination is a directory.")
    except PermissionError:
        st.error("Permission denied.")
    except FileNotFoundError:
        st.error(f"Source file {source_path} not found.")
    except Exception as e:
        st.error(f"Error occurred while copying file: {e}")


    #st.info("finish copy")
    # add resource
    ttl_for_registering_the_file_upload = """
    @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
    @prefix prov:   <http://www.w3.org/ns/prov#> .

    [] a prov:Entity ; 
        enexa:experiment <{}> ; 
        enexa:location "{}/{}" .
    """.format(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename)

    ttl_for_registering_the_file_upload_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_file_upload)

    # with st.expander("➕ " + label_for_addition):
    #     st.code(ttl_for_registering_the_file_upload, language="turtle")
    #     st.code(ttl_for_registering_the_file_upload_as_jsonld, language="json")

    response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld,
                             headers={"Content-Type": "application/ld+json", "Accept": "text/turtle"})
    #st.info("file added and the response is :" + str(response))
    return response


def start_cel_service_step(experiment_resource, tripleStoreIRI, embedding_csv_iri):
    #st.info(        "starting cel service" + "experiment_resource :" + experiment_resource + "tripleStoreIRI :" + tripleStoreIRI + "embedding_csv_iri :" + embedding_csv_iri)

    cel_service_experiment_data = experiment_data  # create_experiment_data()
    cel_service_experiment_resource = cel_service_experiment_data["experiment_iri"]
    cel_service_experiment_directory = cel_service_experiment_data["experiment_folder"]
    cel_service_relative_file_location_inside_enexa_dir = cel_service_experiment_directory

    response_cel_step_deployed = start_cel_service_module(experiment_resource, tripleStoreIRI)
    container_id_cel_step_deployed = extract_X_from_turtle(response_cel_step_deployed.text,
                                                           "http://w3id.org/dice-research/enexa/ontology#containerId")

    container_name_cel_step_deployed = extract_X_from_turtle(response_cel_step_deployed.text,
                                                             "http://w3id.org/dice-research/enexa/ontology#containerName")

    # cel_deployed_module_instance_iri = extract_id_from_turtle(response_cel_step_deployed.text)

    read_container_logs_stop_when_reach_x(container_id_cel_step_deployed,"default",
                                          "Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)")

    # send , embedding_csv_iri, cel_trained_file_kge_iri with get request

    url = "http://" + container_name_cel_step_deployed + ":8000/cel"

    st.info("url is :"+url)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    label_dict = {
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

    # train    'http://0.0.0.0:8000/cel' '{"pos":["http://www.benchmark.org/family#F2F14"], "neg":["http://www.benchmark.org/family#F10F200"], "model":"Drill","path_embeddings":"embeddings/Keci_entity_embeddings.csv"}'

    locationOfCSVFile = extract_X_from_triplestore("http://w3id.org/dice-research/enexa/ontology#location",
                                                   META_DATA_ENDPOINT,
                                                   META_DATA_GRAPH_NAME,
                                                   embedding_csv_iri)

    locationOfCSVFile = locationOfCSVFile.replace('enexa-dir:/', '/enexa')

    # evaluate 'http://0.0.0.0:8000/cel' '{"pos":["http://www.benchmark.org/family#F2F14"], "neg":["http://www.benchmark.org/family#F10F200"], "model":"Drill","pretrained":"pretrained","path_embeddings":"embeddings/Keci_entity_embeddings.csv"}'
    # First example: BASF, Adidas vs. Bosch
    data = {
        "pos":["http://www.wikidata.org/entity/Q3895","http://www.wikidata.org/entity/Q180855"],
        "neg":["http://www.wikidata.org/entity/Q483915","http://www.wikidata.org/entity/Q1359568","http://www.wikidata.org/entity/Q169167","http://www.wikidata.org/entity/Q192334","http://www.wikidata.org/entity/Q695087","http://www.wikidata.org/entity/Q20165", "http://www.wikidata.org/entity/Q2087161"],
        "model": "Drill",
        "max_runtime": 180,
        "iter_bound": 2,
        "path_to_pretrained_drill": "pretrained_drill",
        "path_embeddings": locationOfCSVFile
    }

    csv_file_path = 'wikidata-info.csv'
    wikidata_df = pd.read_csv(csv_file_path)
    wikidata_label_dict = pd.Series(wikidata_df.label.values, index=wikidata_df.id).to_dict()

    #st.info("Training started")
    # Sending the GET request with headers and JSON data
    response = requests.get(url, headers=headers, data=json.dumps(data))

    # Check for successful response
    if response.status_code != 200:

        # Handle error
        st.error(f"Error: {response.text}")
        st.error(response)

    #st.info("Evaluating")

    data = {
        "pos": ["http://www.wikidata.org/entity/Q3895", "http://www.wikidata.org/entity/Q180855"],
        "neg": ["http://www.wikidata.org/entity/Q483915","http://www.wikidata.org/entity/Q1359568","http://www.wikidata.org/entity/Q169167","http://www.wikidata.org/entity/Q192334","http://www.wikidata.org/entity/Q695087","http://www.wikidata.org/entity/Q20165", "http://www.wikidata.org/entity/Q2087161"],
        "model": "Drill",
        "max_runtime": 180,
        "iter_bound": 2
    }
    #st.info(data)
    response = requests.get(url, headers=headers, data=json.dumps(data))
    first_example_label = "$E^+=\\Big\{$Adidas AG (Q3895), Heineken (Q180855)$\\Big\}, E^-=\\Big\{$Nike (Q483915), Alibaba Group (Q1359568), Metro AG (Q169167), University of North Carolina at Chapel Hill (Q192334), Mars Incorporated (Q695087), Nissan Motor Co. Ltd. (Q20165), Heineken Experience (Q2087161)$\\Big\}$"
    # Check for successful response
    if response.status_code == 200:
        # Process the JSON response data
        #st.info(response.json())
        with st.expander("⚙️ "+first_example_label):
            data_response_first_example = json.loads(response.text)

            # this is a hot fix until CEL module works in a deterministic way
            if (data_response_first_example['Results'][0]['Prediction'].startswith("∃ P859⁻")):
                data_response_first_example['Results'][0]['Prediction'] = "∃ P859⁻.(∃ P366⁻.⊤)"

            for item in data_response_first_example['Results']:
                # this is a hot fix until CEL module works in a deterministic way
                if (item['Prediction'] == "∃ P859⁻.(≥ 1 P366⁻.⊤)"):
                    item['Prediction'] = "∃ P859⁻.(∃ P366⁻.⊤)"

                item['Prediction with labels'] = process_verbalization(item['Prediction'], wikidata_label_dict)



            df = pd.DataFrame(data_response_first_example['Results'])
            df = df[['Rank', 'Prediction', 'F1', 'Prediction with labels']]

            st.table(df.set_index('Rank'))
    else:
        # Handle error
        st.error(f"Error: {response.text}")
        st.error(response)

    #st.info("Evaluating second example ")

    data = {
        "pos": ["http://www.wikidata.org/entity/Q483915", "http://www.wikidata.org/entity/Q1359568", "http://www.wikidata.org/entity/Q20165"],
        "neg": ["http://www.wikidata.org/entity/Q3895", "http://www.wikidata.org/entity/Q180855","http://www.wikidata.org/entity/Q169167"],
        "model": "Drill",
        "max_runtime": 180,
        "iter_bound": 2,
        "path_to_pretrained_drill": "pretrained_drill",
        "path_embeddings": locationOfCSVFile
    }
    #st.info(data)
    response = requests.get(url, headers=headers, data=json.dumps(data))
    second_example_label = "$E^+=\\Big\{$Nike (Q483915), Alibaba Group (Q1359568), Nissan Motor Co. Ltd. (Q20165)$\\Big\}, E^-=\\Big\{$Adidas AG (Q3895), Dickies (Q114913), Metro AG (Q169167)$\\Big\}$"
    # Check for successful response
    if response.status_code == 200:
        # Process the JSON response data
        #st.info(response.json())
        with st.expander("⚙️ "+second_example_label):
            data_response_second_example = json.loads(response.text)

            for item in data_response_second_example['Results']:
                item['Prediction with labels'] = process_verbalization(item['Prediction'], wikidata_label_dict)

            df = pd.DataFrame(data_response_second_example['Results'])
            df = df[['Rank', 'Prediction', 'F1', 'Prediction with labels']]

            st.table(df.set_index('Rank'))
    else:
        # Handle error
        st.error(f"Error: {response.text}")
        st.error(response)


    # # Sending the GET request with headers and JSON data
    # response = requests.get(url, headers=headers, json=json.dumps(data))
    #
    # # Check for successful response
    # if response.status_code == 200:
    #     # Process the JSON response data
    #     st.info(response.json())
    #     st.info("please wait for explanation module . . . ")
    #     json_file_for_this_example = """{    "learned_expression": "Subsidiary (Q658255)",    "positive_examples": {        "Tommy Hilfiger (Q634881)": "American multinational corporation that designs and manufactures apparel"    },    "negative_examples": {        "Dickies (Q114913)": "company that manufactures and sells work-related clothing and other accessories",        "Globus (Q457503)": "German multinational hypermarket, home improvement and electronics retail chain"    },    "source": "https://en.wikipedia.org",    "extraction_model": "https://huggingface.co/ibm/knowgl-large",    "learned_by": "Neural Class Expression Learner"}""";
    #     start_explanation_module(json_file_for_this_example)
    #
    # else:
    #     st.error(f"Error: {response.text}")
    #     st.error(response)
    st.subheader("6 Running explaining module")
    #open explanation module
    explanation_json_file = {
        "learned_expression": data_response_first_example['Results'][0]['Prediction with labels'],
        "positive_examples": {
            "Adidas AG (Q3895)": "German multinational corporation",
            "Heineken (Q180855)": "Dutch beer company"
        },
        "negative_examples": {
            "Nike (Q483915)": "American athletic equipment company",
            "Alibaba Group (Q1359568)": "Chinese multinational technology company",
            "Metro AG (Q169167)": "German wholesale company",
            "University of North Carolina at Chapel Hill (Q192334)": "public research university in Chapel Hill, North Carolina, United States",
            "Mars, Incorporated (Q695087)": "American global food company and manufacturer",
            "Nissan Motor Co. Ltd. (Q20165)": "Japanese company",
            "Heineken Experience (Q2087161)": "industrial museum in Amsterdam, Netherlands"
        },
        "source": "https://en.wikipedia.org",
        "extraction_model": "https://huggingface.co/ibm/knowgl-large",
        "learned_by": "Neural Class Expression Learner"
    }
    #st.info("start explanation"+ json.dumps(explanation_json_file))
    start_explanation_module(experiment_resource, explanation_json_file , "first example")


    ###### second example
    # open explanation module
    explanation_json_file = {
        "learned_expression": data_response_second_example['Results'][0]['Prediction with labels'],
        "positive_examples": {
            "Nike (Q483915)": "American athletic equipment company",
            "Alibaba Group (Q1359568)": "Chinese multinational technology company",
            "Nissan Motor Co. Ltd. (Q20165)": "Japanese company"
        },
        "negative_examples": {
            "Adidas AG (Q3895)": "German multinational corporation",
            "Heineken (Q180855)": "Dutch beer company",
            "Metro AG (Q169167)": "German wholesale company"
        },
        "source": "https://en.wikipedia.org",
        "extraction_model": "https://huggingface.co/ibm/knowgl-large",
        "learned_by": "Neural Class Expression Learner"
    }
    # st.info("start explanation"+ json.dumps(explanation_json_file))
    start_explanation_module(experiment_resource, explanation_json_file, "second example")


    st.success("Done!", icon="🏁")


def process_verbalization(expression, wikidata_label_dict):
    parts = []
    last_end_pos = 0
    # Iterate over all matches
    for match in WIKIDATA_PATTERN.finditer(expression):
        # Add the string in front of the match
        parts.append(expression[last_end_pos:match.start()])
        last_end_pos = match.end()
        found_id = expression[match.start():last_end_pos]
        # Replace with the Wikidata IRI label
        # parts.append("{0} ({1})".format(wikidata_label_dict[found_id],found_id))
        parts.append("{0}".format(wikidata_label_dict[found_id]))
    # Add the remaining string
    parts.append(expression[last_end_pos:])
    return ''.join(parts)

def perform_cel(data, label, url, headers, label_dict):
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_data = response.json()
    # Print response data
    with st.expander("⚙️ " + label):
        st.markdown(cel_response_to_markdown(response_data, label_dict))


def cel_response_to_markdown(response_data, label_dict):
    output = ""
    st.info(response_data)
    for rated_ce in response_data["Results"]:
        rated_ce[0] = create_pretty_ce(rated_ce[0], label_dict)
    st.table(pandas.DataFrame(data=response_data["prediction"], columns=("Class Expression", "F1-Score")))
    # for rated_ce in response_data["prediction"]:
    #    output += "|" + str(rated_ce[1]) + "|" + create_pretty_ce(rated_ce[0], label_dict) + "|\n"
    return output


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
             logging.info("Unknown entity ID: " + c)
    return class_expression


def start_cel_step(experiment_resource, tripleStoreIRI):
    st.subheader("5️ Running class expression learning")
    #st.info("Starting class expression learning ... experiment_resource : " + str(        experiment_resource) + " tripleStoreIRI: " + str(tripleStoreIRI))
    cel_experiment_data = experiment_data  # create_experiment_data()

    cel_experiment_resource = cel_experiment_data["experiment_iri"]
    cel_experiment_directory = cel_experiment_data["experiment_folder"]
    cel_relative_file_location_inside_enexa_dir = cel_experiment_directory
    # add ontology
    # embedding_csv_iri = extract_embeddings_csv_from_triplestore(META_DATA_ENDPOINT, META_DATA_GRAPH_NAME,experiment_resource)

    # add embedding_csv_iri
    add_preproccessed_embedding_csv = add_module_configuration_to_enexa_service(
        cel_experiment_resource,
        cel_relative_file_location_inside_enexa_dir,
        "Keci_embeddings_group1-data.csv",
        label_for_addition="Adding Keci embedding model")
    if (add_preproccessed_embedding_csv.status_code != 200):
        st.error("cannot add file")
    else:
        # st.info("Keci_entity_embeddings file add to servcie" + add_preproccessed_embedding_csv.text + " ")

        embedding_csv_iri = extract_id_from_turtle(add_preproccessed_embedding_csv.text)
        # st.info("starting CEL training module ...")
        start_cel_service_step(experiment_resource, tripleStoreIRI, embedding_csv_iri)
        # response_cel_step = start_cel_module(experiment_resource, owl_file_iri, embedding_csv_iri)
        # if (response_cel_step.status_code != 200):
        #     st.error("error in running transform module")
        # else:
        #     cel_step_module_instance_iri = extract_id_from_turtle(response_cel_step.text)
        #     if cel_step_module_instance_iri:
        #         logging.info("id:", cel_step_module_instance_iri)
        #     else:
        #         logging.info("No id found in JSON-LD")
        #         st.error("No iri for the last module found")
        #     # st.info("starting CEL training module started")
        #     # st.info("cel_step_module_instance_iri is :" + cel_step_module_instance_iri)
        #     # st.info("experiment_resource is :" + experiment_resource)
        #
        #     container_id_cel_step = extract_X_from_turtle(response_cel_step.text,
        #                                                   "http://w3id.org/dice-research/enexa/ontology#containerId")
        #     # st.info("container_id_embeddings_step is : " + container_id_cel_step)
        #     print_container_logs(container_id_cel_step)
        #
        #     st.write(
        #         "✅ Module instance ({}) finished successfully.".format(
        #             container_id_cel_step))
        #
        #     cel_trained_file_kge_iri = extract_cel_trained_kge_from_triplestore(META_DATA_ENDPOINT,
        #                                                                         META_DATA_GRAPH_NAME,
        #                                                                         cel_step_module_instance_iri)
        #
        #     start_cel_service_step(experiment_resource, owl_file_iri, embedding_csv_iri, cel_trained_file_kge_iri)


def start_cel_transform_step(experiment_resource, repaired_abox_iri, wikidata5m_iri):
    # transform nt file to owl
    # st.info("starting cel transform step experiment_resource : "+experiment_resource+" repaired_abox_iri : " +repaired_abox_iri+" wikidata5m_iri : "+wikidata5m_iri)
    #st.info("starting cel transform step experiment_resource : " + experiment_resource + " repaired_abox_iri : " + repaired_abox_iri + " wikidata5m_iri : " + wikidata5m_iri)
    cel_transform_experiment_data = experiment_data  # create_experiment_data()
    cel_transform_experiment_resource = cel_transform_experiment_data["experiment_iri"]
    cel_transform_experiment_directory = cel_transform_experiment_data["experiment_folder"]
    cel_transform_relative_file_location_inside_enexa_dir = cel_transform_experiment_directory

    # add reduced kg as owl file w5M-rdf-1.owl
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
    # responce_add_wikidata5m = add_module_configuration_to_enexa_service(
    #    cel_transform_experiment_resource,
    #    cel_transform_relative_file_location_inside_enexa_dir,
    #    DATASET_NAME)
    # if (responce_add_wikidata5m.status_code != 200):
    #    st.error("cannot add file: " + DATASET_NAME)
    # else:
    #    st.info("file add " + responce_add_wikidata5m.text + " ")

    #    wikidata5m_iri = extract_id_from_turtle(responce_add_wikidata5m.text)
    response_transform_step = start_cel_transform_module(experiment_resource, repaired_abox_iri, wikidata5m_iri)
    # st.info(str(response_transform_step.status_code))
    if (response_transform_step.status_code != 200):
        st.error("error in running cel transform module")
    else:
        # st.info(" start cel transform strp")
        cel_transform_step_module_instance_iri = extract_id_from_turtle(response_transform_step.text)
        # st.info(" cel_transform_step_module_instance_iri " + cel_transform_step_module_instance_iri)

        if cel_transform_step_module_instance_iri:
            logging.info("id:"+ cel_transform_step_module_instance_iri)
        else:
            logging.info("No id found in JSON-LD")
            st.error("No iri for the last module found")
        # st.info("cel_transform_step_module_instance_iri is :" + cel_transform_step_module_instance_iri)
        # st.info("experiment_resource is :" + experiment_resource)

        # st.success("get status experiment_resource is : "+experiment_resource)
        response_check_module_instance_status = get_the_status(SERVER_ENDPOINT,
                                                               cel_transform_step_module_instance_iri,
                                                               experiment_resource)
        logging.info("status is : " + response_check_module_instance_status.text)
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
            logging.info("status is : " + response_check_module_instance_status.text)
            time.sleep(SLEEP_IN_SECONDS)
            elapsedTime = elapsedTime + SLEEP_IN_SECONDS
            # Update the text of the info box in the session state
            # st.session_state["info_box_text"] = "Waiting for result ({} sec) ... ".format(elapsedTime)

        st.write(
            "✅ Module instance ({}) finished successfully.".format(
                cel_transform_step_module_instance_iri))

        # TODO SHOULD NOT BE HARDCODED
        owl_file_iri = extract_output_from_triplestore(META_DATA_ENDPOINT,
                                                       META_DATA_GRAPH_NAME,
                                                       cel_transform_step_module_instance_iri)
        start_cel_step(experiment_resource, owl_file_iri)


def start_tentris(experiment_resource, repaired_a_box_iri):
    st.subheader("3️ Running knowledge graph embedding module")
    st.write("This step is skipped in this demo. Instead we use a pre-generated model.")
    st.subheader("4️ Starting Tentris ")
    tentris_experiment_data = experiment_data  # create_experiment_data()
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
        st.error("cannot add file: " + DATASET_NAME_TENTRIS)
    else:
        # st.info("data set add to service " + responce_add_wikidata5m.text + " ")

        wikidata5m_unfiltered_iri = extract_id_from_turtle(responce_add_wikidata5m.text)

        response_tentris_step = start_tentris_module(experiment_resource, wikidata5m_unfiltered_iri)

        container_id_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
                                                                   "http://w3id.org/dice-research/enexa/ontology#containerId")

        container_name_tentris_step_deployed = extract_X_from_turtle(response_tentris_step.text,
                                                                     "http://w3id.org/dice-research/enexa/ontology#containerName")

        read_container_logs_stop_when_reach_x(container_id_tentris_step_deployed,"default", "0.0.0.0:9080")

        #st.write("✅ Tentris is ready.")
        # st.success("Tentris is ready",icon="✅")
        triple_store_endpoint = "http://" + container_name_tentris_step_deployed + ":9080/sparql"

        #add_tentris_endpoint_responce = add_tentris_endpoint_to_metadata(experiment_resource, triple_store_endpoint)

        # # BASF, Adidas, BOSCH, Tommy Hilfiger, Dickies, Globus, Tesco, Lacoste, Foot Locker, Bohemia Interactive
        # all_iri = ["https://www.wikidata.org/wiki/Q9401", "https://www.wikidata.org/wiki/Q3895",
        #            "https://www.wikidata.org/wiki/Q234021", "https://www.wikidata.org/wiki/Q634881",
        #            "https://www.wikidata.org/wiki/Q114913", "https://www.wikidata.org/wiki/Q457503",
        #            "https://www.wikidata.org/wiki/Q487494", "https://www.wikidata.org/wiki/Q309031",
        #            "https://www.wikidata.org/wiki/Q63335", "https://www.wikidata.org/wiki/Q890779"]
        #
        # # query_str_first = "CONSTRUCT {    ?s ?p ?o .} WHERE {    VALUES ?s { "+all_iri+" }    ?s ?p ?o .}"
        # subject_graph = Graph()
        # for iri in all_iri:
        #     query_str_first = "SELECT ?p ?o WHERE {  <" + iri + "> ?p ?o .} "
        #     logging.info("first query " + query_str_first)
        #     # st.info("query is : " + query_str_first + " sending to Tentris")
        #     subject_graph += run_query_triplestore_subject(query_str_first, triple_store_endpoint, iri)
        #
        # object_graph = Graph()
        # for iri in all_iri:
        #     query_str_second = "SELECT ?s ?p WHERE {  ?s ?p <" + iri + "> .}"
        #     logging.info("second query " + query_str_second)
        #     # st.info("query is : " + query_str_second+ " sending to Tentris")
        #     object_graph += run_query_triplestore_object(query_str_second, triple_store_endpoint, iri)
        #
        # subject_graph += object_graph
        #
        # num_triples = len(subject_graph)
        # # st.info("concat the graphs the graph size is " + str(num_triples))
        #
        # filtered_wikidata5m_file_name = str(uuid.uuid4()) + ".nt"
        # filtered_wikidata5m_file_path = ENEXA_SHARED_DIRECTORY + "/" + filtered_wikidata5m_file_name
        # # st.info("graph will be save here : "+filtered_wikidata5m_file_path)
        # # Serialize the RDF graph as an .nt file
        #
        # subject_graph.serialize(destination=filtered_wikidata5m_file_path, format="nt")
        # # with open(filtered_wikidata5m_file_path, 'wb') as f:
        # #     f.write(firstpartGraph.serialize(format='nt'))
        # # #save as file
        # # st.success("file saved")
        #
        # # f = open(filtered_wikidata5m_file_path , 'w')
        # # f.write(firstpart)
        # # f.write(secondpart)
        # # f.close()
        # # add to service
        # responce_add_filteredwikidata5m = add_module_configuration_to_enexa_service(
        #     tentris_experiment_resource,
        #     tentris_relative_file_location_inside_enexa_dir,
        #     filtered_wikidata5m_file_name,
        #     label_for_addition="Adding generated Wikidata5M subset file")
        # if (responce_add_wikidata5m.status_code != 200):
        #     st.error("cannot add file: " + filtered_wikidata5m_file_path)
        # else:
        #     st.info("graph add to service ")
        #
        #     wikidata5m_iri = extract_id_from_turtle(responce_add_filteredwikidata5m.text)

        #     start_cel_transform_step(experiment_resource, repaired_a_box_iri, wikidata5m_iri)
        tentris_iri = extract_id_from_turtle(response_tentris_step.text)
        #st.info("tentris is : "+tentris_iri)
        start_cel_step(experiment_resource, tentris_iri)


# def start_embeddings_step(experiment_resource, iri_nt_file_from_preprocess_embedding):
#     st.info("starting embeding step")
#     embeddings_experiment_data = experiment_data # create_experiment_data()
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
#             logging.info("id:", embeddings_step_module_instance_iri)
#         else:
#             logging.info("No id found in JSON-LD")
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
#     transform_experiment_data = experiment_data # create_experiment_data()
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
#                     logging.info("id:", transform_step_module_instance_iri)
#                 else:
#                     logging.info("No id found in JSON-LD")
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
#     embedding_preproc_experiment_data = experiment_data # create_experiment_data()
#     embedding_preproc_experiment_resource = embedding_preproc_experiment_data["experiment_iri"]
#     embedding_preproc_experiment_directory = embedding_preproc_experiment_data["experiment_folder"]
#     embedding_preproc_relative_file_location_inside_enexa_dir = embedding_preproc_experiment_directory
#     responce_embedding_preproc_step = start_preprocess_module(experiment_resource, not_processed_data_iri)
#     if (responce_embedding_preproc_step.status_code != 200):
#         st.error("error in preprocess data")
#     else:
#         embedding_preproc_step_module_instance_iri = extract_id_from_turtle(responce_embedding_preproc_step.text)
#         if embedding_preproc_step_module_instance_iri:
#             logging.info("embedding_preproc_step_module_instance_iri id:", embedding_preproc_step_module_instance_iri)
#         else:
#             logging.info("No id found in embedding_preproc_step_module_instance_iri")
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

def read_file(file_path, num_lines):  # , keyword):
    # try:
    #     found_keyword = False
    #     line_C = 0
    #     lines = []
    #     with open(file_path, 'r') as file:
    #         for line in file:
    #             if found_keyword:
    #                 lines.append(line)
    #                 line_C = line_C + 1
    #                 if line_C == num_lines:
    #                     break
    #             elif keyword in line:
    #                 lines.append(line)
    #                 found_keyword = True
    #         return lines
    # except Exception as e:
    #     return [str(e)]
    try:
        with open(file_path, 'r') as in_file:
            all_lines = in_file.readlines()
        return all_lines[:num_lines]
    except Exception as e:
        return [str(e)]


def start_repair_step(experiment_resource, module_instance_id):
    st.subheader("2️ Running knowledge graph repair module")
    #st.info("experiment_resource : "+experiment_resource)

    second_step_experiment_data = experiment_data  # create_experiment_data()
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
        "1-ontology_version_1.ttl",
        label_for_addition="Adding ontology file")
    if (second_step_responce_configFile_resource.status_code != 200):
        st.error("cannot add file")
    else:
        # st.info("T-box file add " + second_step_responce_configFile_resource.text + " ")

        uploadedFileId = extract_id_from_turtle(second_step_responce_configFile_resource.text)

        # st.info("uploadedFileId " + uploadedFileId)
        # st.info("starting fixing module . . .")
        response_second_step = start_kg_fixing_module(experiment_resource, module_instance_id, uploadedFileId)

        if response_second_step.status_code != 200:
            st.error("Error while starting Knowldge Graph Fixing  task: {}.".format(response_start_module))
        else:
            second_step_module_instance_iri = extract_id_from_turtle(response_second_step.text)
            if second_step_module_instance_iri:
                logging.info("id:"+ second_step_module_instance_iri)
            else:
                logging.info("No id found in JSON-LD")
            # st.info("fixing module started")
            # st.info("module_instance_id is :" + second_step_module_instance_iri)
            # st.info("experiment_resource is :" + experiment_resource)

            container_id_fixing_module = extract_X_from_turtle(response_second_step.text,
                                                               "http://w3id.org/dice-research/enexa/ontology#containerId")
            # st.info("container_id_fixing_module is : " + container_id_fixing_module)
            changedlines = print_container_logs(container_id_fixing_module)
            with st.expander("🔧 Fixed triples"):
                for change in changedlines:
                    st.text(change)

            st.write(
                "✅ Module instance ({}) finished successfully.".format(
                    second_step_module_instance_iri))
            # st.success(
            #    "Module instance ({}) finished successfully.".format(
            #        second_step_module_instance_iri), icon="✅")

            # repaired_A_box_iri = extract_X_from_triplestore("http://w3id.org/dice-research/enexa/module/kg-fixing/result/fixedKG", META_DATA_ENDPOINT,
            #   META_DATA_GRAPH_NAME,
            #  second_step_module_instance_iri)
            # start_embeddings_transform_step(experiment_resource, second_step_module_instance_iri)
            # start_embedding_data_preprocess(experiment_resource, repaired_A_box_iri)

            # skip embeddings
            repaired_a_box_iri = extract_id_from_turtle(response_second_step.text)
            # st.info("repaired a box iri is : " + str(repaired_a_box_iri))
            # start_cel_transform_step(experiment_resource, repaired_a_box_iri)
            start_tentris(experiment_resource, repaired_a_box_iri)


def print_container_logs(pod_uid, namespace="default", timeout=300, interval=5):
    returnlines = []

    try:
        # Load in-cluster config if running inside a pod, or kubeconfig if running externally
        config.load_incluster_config()  # If running inside Kubernetes
        # config.load_kube_config()  # Uncomment if running outside the cluster (e.g., locally)

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Get the list of pods in the namespace to match by UID
        pods = v1.list_namespaced_pod(namespace=namespace)
        pod_name = None

        # Find the pod by its UID
        for pod in pods.items:
            if pod.metadata.uid == pod_uid:
                pod_name = pod.metadata.name
                break

        if not pod_name:
            st.error(f"No pod found with UID {pod_uid}")
            return returnlines

        # Start waiting for the pod to be in the Running state
        end_time = time.time() + timeout  # Set the timeout limit
        while time.time() < end_time:
            pod_status = v1.read_namespaced_pod_status(name=pod_name, namespace=namespace)

            # Check if all containers are ready
            container_statuses = pod_status.status.container_statuses
            if container_statuses and all([container.ready for container in container_statuses]):
                break  # All containers are ready

            # Display a message and wait for the specified interval
            st.info(
                f"Waiting for pod {pod_name} to start. Current phase: {pod_status.status.phase}. Checking again in {interval} seconds...")
            time.sleep(interval)  # Wait for the interval before checking again

        else:
            # If the loop finished without breaking, it means the timeout occurred
            st.error(f"Timed out waiting for pod {pod_name} to start.")
            return returnlines

        # At this point, the pod should be running; get the logs for the pod
        with st.expander("📃 Pod logs (" + str(pod_name) + "):"):
            logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, follow=True, _preload_content=False,
                                              pretty=True)
            for log_line in logs:
                log_line = log_line.decode("utf-8")  # Decode byte log to string
                if log_line.startswith("INFO: ******* Found inconsistency:") or log_line.startswith(
                        "INFO: ******* Apply Sound fix:"):
                    returnlines.append(log_line)
                st.text(log_line)

    except client.exceptions.ApiException as e:
        st.error("An error occurred when retrieving pod logs: " + str(e))
    except Exception as e:
        st.error("An error occurred: " + str(e))

    return returnlines


# def print_container_logs(container_id):
#     returnlines = []
#     try:
#         client = docker.from_env()
#         container = client.containers.get(container_id)
#         with st.expander("📃 Module logs (" + str(container_id) + "):"):
#             for log_line in container.logs(stream=True):
#                 if str(log_line.decode("utf-8")).startswith("INFO: ******* Found inconsistency:") or str(
#                         log_line.decode("utf-8")).startswith("INFO: ******* Apply Sound fix:"):
#                     returnlines.append(log_line.decode("utf-8"))
#                 st.text(log_line.decode("utf-8"))
#     except docker.errors.NotFound:
#         st.error("Container with ID " + str(container_id) + " not found.")
#     except Exception as e:
#         st.error("An error occurred: " + str(e))
#     return returnlines


# def read_container_logs_stop_when_reach_x(container_id, x):
#     # st.info("looking for "+x)
#     returnlines = []
#     try:
#         client = docker.from_env()
#         container = client.containers.get(container_id)
#         with st.expander("📃 Module logs (" + str(container_id) + "):"):
#             for log_line in container.logs(stream=True):
#                 st.text(log_line)
#                 if x in str(log_line.decode("utf-8")):
#                     return
#     except docker.errors.NotFound:
#         st.error("Container with ID " + str(container_id) + " not found.")
#     except Exception as e:
#         st.error("An error occurred: " + str(e))
#     return returnlines


def read_container_logs_stop_when_reach_x(pod_uid, namespace="default", x="", timeout=300, interval=5):
    returnlines = []

    try:
        # Load in-cluster config if running inside a pod, or kubeconfig if running externally
        config.load_incluster_config()  # If running inside Kubernetes
        # config.load_kube_config()  # Uncomment if running outside the cluster (e.g., locally)

        # Create a Kubernetes API client
        v1 = client.CoreV1Api()

        # Get the list of pods in the namespace to match by UID
        pods = v1.list_namespaced_pod(namespace=namespace)
        pod_name = None

        # Find the pod by its UID
        for pod in pods.items:
            if pod.metadata.uid == pod_uid:
                pod_name = pod.metadata.name
                break

        if not pod_name:
            st.error(f"No pod found with UID {pod_uid}")
            return returnlines

        # Wait for the pod to be in the Running state
        end_time = time.time() + timeout  # Set the timeout limit
        while time.time() < end_time:
            pod_status = v1.read_namespaced_pod_status(name=pod_name, namespace=namespace)

            # Check if all containers are ready
            container_statuses = pod_status.status.container_statuses
            if container_statuses and all([container.ready for container in container_statuses]):
                break  # All containers are ready

            # Display a message and wait for the specified interval
            st.info(
                f"Waiting for pod {pod_name} to start. Current phase: {pod_status.status.phase}. Checking again in {interval} seconds...")
            time.sleep(interval)  # Wait for the interval before checking again

        else:
            # If the loop finished without breaking, it means the timeout occurred
            st.error(f"Timed out waiting for pod {pod_name} to start.")
            return returnlines

        # At this point, the pod should be running; get the logs for the pod
        with st.expander("📃 Module logs (" + str(pod_name) + "):"):
            logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, follow=True, _preload_content=False)
            for log_line in logs:
                log_line = log_line.decode("utf-8")  # Decode byte log to string
                st.text(log_line)
                returnlines.append(log_line)  # Store log line
                if x in log_line:  # Stop when the specific log line is found
                    st.info(f"Stopped reading logs for {pod_name} as '{x}' was found.")
                    return returnlines

    except client.exceptions.ApiException as e:
        st.error("An error occurred when retrieving pod logs: " + str(e))
    except Exception as e:
        st.error("An error occurred: " + str(e))

    return returnlines


def get_the_status(SERVER_ENDPOINT, module_instance_iri, experiment_resource):
    status_container_endpoint = SERVER_ENDPOINT + "/container-status"
    status_module_message_as_json = {
        "moduleInstanceIRI": module_instance_iri,
        "experimentResource": experiment_resource
    }
    # st.info(json.dumps(status_module_message_as_json))
    return requests.post(status_container_endpoint, data=json.dumps(status_module_message_as_json),
                         headers={"Content-Type": "application/json", "Accept": "text/turtle"})

    # return requests.get(SERVER_ENDPOINT + "/container-status?moduleInstanceIRI=" + module_instance_iri + "&experimentIRI=" + experiment_resource)


if uploaded_files is not None and uploaded_files != []:
    for uploaded_file in uploaded_files:
        # st.subheader(" Preparing...")
        st.subheader("1️ Running extraction module")

        skip_extraction = False  # JUST FOR DEBUGGING. SHOULD BE FALSE!!!
        extraction_previous_run = "http://example.org/enexa/4d4c7922-7ae8-4cb1-8e49-394d6670634b"
        # create experiment instance
        experiment_data = create_experiment_data()

        experiment_resource = experiment_data["experiment_iri"]
        experiment_directory = experiment_data["experiment_folder"]
        # TODO
        # relative_file_location_inside_enexa_dir = ENEXA_SHARED_DIRECTORY + "/" + experiment_directory
        relative_file_location_inside_enexa_dir = experiment_directory

        # add resource config file
        # experiment_resource, relative_file_location_inside_enexa_dir,uploaded_filename
        st.info("debug: start copy the generation parameters json experiment_resource is"+str(experiment_resource)+" relative_file_location_inside_enexa_dir is "+str(relative_file_location_inside_enexa_dir))
        responce_configFile_resource = add_module_configuration_to_enexa_service(experiment_resource,
                                                                                 relative_file_location_inside_enexa_dir,
                                                                                 "generation_parameters.json",
                                                                                 label_for_addition="Adding extraction parameters file")
        if responce_configFile_resource.status_code != 200:
            st.error("error in upload configuration file ")
        else:

            st.success("ENEXA generation_parameters.json file upload registered successfully.")
            # st.info(responce_configFile_resource.text)
            # configFile_resource = extract_id_from_turtle(responce_configFile_resource.text)
            # st.success("configFile_resource is task: {}".format(configFile_resource))
            generation_parameters_IRI = extract_id_from_turtle(responce_configFile_resource.text)
            st.info("generation_parameters_IRI is : " +generation_parameters_IRI)
            uploaded_filename = uploaded_file.name.replace(" ", "_")
            uploaded_file_content = uploaded_file.read()

            # UI file upload
            st.info("write file to folder ENEXA_WRITEABLE_DIRECTORY is "+ENEXA_WRITEABLE_DIRECTORY)
            write_file_to_folder(ENEXA_WRITEABLE_DIRECTORY, uploaded_filename, uploaded_file_content)
            st.info(
                "File" + str(uploaded_filename) + " uploaded successfully and stored in experiment's directory:" + str(
                    ENEXA_WRITEABLE_DIRECTORY))
            logging.info("File"+str(uploaded_filename)+" uploaded successfully and stored in experiment's directory:"+str(ENEXA_WRITEABLE_DIRECTORY))
            #logging.info("File {} uploaded successfully and stored in experiment's directory: {}".format(uploaded_filename,ENEXA_WRITEABLE_DIRECTORY))
            # st.info("File :\" {} \" uploaded successfully and stored in experiment's directory: \" {} \" ".format(                uploaded_filename,                ENEXA_WRITEABLE_DIRECTORY))

            # send configuration file to ENEXA service
            # print ("*****relative_file_location_inside_enexa_dir is :"+relative_file_location_inside_enexa_dir)

            # st.info("ENEXA_WRITEABLE_DIRECTORY is :" + ENEXA_WRITEABLE_DIRECTORY)
            # st.info("relative_file_location_inside_enexa_dir is :" + relative_file_location_inside_enexa_dir)

            st.info("write file to folder relative_file_location_inside_enexa_dir is " + relative_file_location_inside_enexa_dir)
            write_file_to_folder(relative_file_location_inside_enexa_dir, uploaded_filename, uploaded_file_content)

            response_adding_uploaded_file = add_resource_to_service(experiment_resource,
                                                                    relative_file_location_inside_enexa_dir,
                                                                    uploaded_filename,
                                                                    label_for_addition="Adding file with uploaded URLs")
            if response_adding_uploaded_file.status_code != 200:
                st.error("Error while registering ENEXA configuration file upload. :cry:")
                st.error(response_adding_uploaded_file.status_code + " " + str(response_adding_uploaded_file))
            else:
                st.success("File : \"" + uploaded_filename + "\" add to Enexa service successfully :ok_hand:")
                urls_to_process_iri = extract_id_from_turtle(response_adding_uploaded_file.text)

                st.info("the ID for added resource (uploaded file) is: "+format(urls_to_process_iri))

                # start a module (i.e., a new container instance of the demanded experiment will be started)
                # st.info ("###configFile_resource is :" + str(generation_parameters_IRI))
                logging.info("Starting extraction module ...")

                if not skip_extraction:
                    response_start_module = start_extraction_module(experiment_resource, urls_to_process_iri,
                                                                    generation_parameters_IRI)

                if not skip_extraction and response_start_module.status_code != 200:
                    st.error("Error while starting ENEXA task: {}.".format(response_start_module))
                else:
                    start_container_endpoint = SERVER_ENDPOINT + "/start-container"
                    st.info("Now, the ENEXA task should be started at the ENEXA platform. Please check the status of your task at the ENEXA platform. Request to {} done.".format(start_container_endpoint))
                    st.info(str(response_start_module))

                    if skip_extraction:
                        module_instance_iri = extraction_previous_run
                    else:
                        module_instance_iri = extract_id_from_turtle(response_start_module.text)
                        container_id = extract_X_from_turtle(response_start_module.text,
                                                             "http://w3id.org/dice-research/enexa/ontology#containerId")

                        st.info("container_id is : " + container_id)
                        print_container_logs(container_id)

                        if module_instance_iri:
                            logging.info("id:"+ module_instance_iri)
                        else:
                            logging.info("No id found in JSON-LD")

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
                    # st.success(
                    #    "Module instance ({}) finished successfully.".format(
                    #        module_instance_iri))

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

                    st.info("debug extracted_file_iri is " + str(extracted_file_iri))

                    file_path = extract_X_from_triplestore(
                        "http://w3id.org/dice-research/enexa/ontology#location", META_DATA_ENDPOINT,
                        META_DATA_GRAPH_NAME,
                        extracted_file_iri)
                    st.info("debug file_path is "+str(file_path))
                    file_path = file_path.replace("enexa-dir:/", ENEXA_SHARED_DIRECTORY)

                    # lines = read_file(file_path, 200, "BASF")
                    lines = read_file(file_path, 200)
                    # single_string = "\n".join(lines)
                    # file_content = ""
                    # for line in lines :
                    #     file_content += line
                    with st.expander("⛏️ Extracted triples (" + file_path + ")"):
                        st.code("".join(lines), language='text')

                    st.write(
                        "✅ Module instance ({}) finished successfully.".format(
                            module_instance_iri))

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

# def send_explanation_req():
#     global experiment_data
#     experiment_data = create_experiment_data()
#     explanation_json_file = {
#         "learned_expression": "Sponsor (P859)",
#         "positive_examples": {
#             "Adidas AG (Q3895)": "German multinational corporation",
#             "Dickies (Q114913)": "company that manufactures and sells work-related clothing and other accessories"
#         },
#         "negative_examples": {
#             "Alibaba Group (Q1359568)": "Chinese multinational technology company",
#             "Metro AG (Q169167)": "German wholesale company",
#             "University of North Carolina at Chapel Hill (Q192334)": "public research university in Chapel Hill, North Carolina, United States"
#         },
#         "source": "https://en.wikipedia.org",
#         "extraction_model": "https://huggingface.co/ibm/knowgl-large",
#         "learned_by": "Neural Class Expression Learner"
#     }
#
#     start_explanation_module("http://example.org/enexa/2026ae4f-951c-4245-9c79-0b4307438e0f",
#                   explanation_json_file)
#
#
# st.button('Explanation', on_click=send_explanation_req)
#
#
#
#
# def send_tentris_req():
#     global experiment_data
#     experiment_data = create_experiment_data()
#     start_tentris("http://example.org/enexa/2026ae4f-951c-4245-9c79-0b4307438e0f",
#                   "http://example.org/enexa/76fe2f40-9fe8-4b1a-9e09-d817e6591dc2")
#
#
# st.button('Continue from Step 4 (Tentris)', on_click=send_tentris_req)
#
#
# def continue_cel_transform():
#     global experiment_data
#     experiment_data = create_experiment_data()
#     experiment_resource = experiment_data["experiment_iri"]
#     repaired_abox_iri = "http://example.org/enexa/40c6f5d2-03a7-4825-b3e9-4cea69f049b7"
#     wikidata5m_iri = "http://example.org/enexa/28e8e590-3b8b-4514-af68-c723be6a7660"
#     #start_cel_transform_step(experiment_resource, repaired_abox_iri, wikidata5m_iri)
#
#
# st.button('CEL transform', on_click=continue_cel_transform)
#
#
# def continue_cel_deploy():
#     global experiment_data
#     experiment_data = create_experiment_data()
#     experiment_resource = experiment_data["experiment_iri"]
#     owl_file_iri = "http://example.org/enexa/13500f8a-c091-4816-8ff5-bc70049bfba4"
#     embedding_csv_iri = "http://example.org/enexa/50c7f2f9-ef34-435b-9443-8589138ad9ed"
#     cel_trained_heuristics_file_iri = "http://example.org/enexa/67ac8bd1-23a1-4495-b171-5fef4579ab57"
#     start_cel_service_step(experiment_resource, owl_file_iri, embedding_csv_iri, cel_trained_heuristics_file_iri)
#
#
# st.button('Continue from Step 5.2 (CEL-Deploy)', on_click=continue_cel_deploy)

# def send_tentris_req():
#     global experiment_data
#     experiment_data = create_experiment_data()
#     start_tentris("http://example.org/enexa/2026ae4f-951c-4245-9c79-0b4307438e0f",
#                   "http://example.org/enexa/76fe2f40-9fe8-4b1a-9e09-d817e6591dc2")
#
#
# st.button('Continue from Step 4 (Tentris)', on_click=send_tentris_req)
