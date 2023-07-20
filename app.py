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
from rdflib import Graph

from decouple import config

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

# config
SERVER_ENDPOINT = config("SERVER_ENDPOINT", default="http://localhost:8080")
ENEXA_SHARED_DIRECTORY = config("ENEXA_SHARED_DIRECTORY", default="/tmp/enexa-shared-directory")
ENEXA_WRITEABLE_DIRECTORY = config("ENEXA_WRITEABLE_DIRECTORY", default=ENEXA_SHARED_DIRECTORY + "/experiments")
SLEEP_IN_SECONDS = config("SLEEP_IN_SECONDS", default=1, cast=int)

# constants
ENEXA_LOGO = "https://raw.githubusercontent.com/EnexaProject/enexaproject.github.io/main/images/enexacontent/enexa_logo_v0.png?raw=true"
ENEXA_EXPERIMENT_SHARED_DIRECTORY_LITERAL = "http://w3id.org/dice-research/enexa/ontology#sharedDirectory"

def write_file_to_folder(folder, filename, content):
    # create directory if not exists
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    with open(folder + "/" + filename, "wb") as f:
        f.write(content)

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

def configuration_file_upload(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename):
  ttl_for_registering_the_file_upload = """
  @prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
  @prefix prov:   <http://www.w3.org/ns/prov#> .

  [] a prov:Entity ; 
      enexa:experiment <{}> ; 
      enexa:location "enexa-dir:{}/{}" .
  """.format(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename)

  ttl_for_registering_the_file_upload_as_jsonld = turtle_to_jsonld(ttl_for_registering_the_file_upload)
  
  with st.expander("Show message for registering the file upload"):
    st.code(ttl_for_registering_the_file_upload, language="turtle")
    st.code(ttl_for_registering_the_file_upload_as_jsonld, language="json")

  response = requests.post(SERVER_ENDPOINT + "/add-resource", data=ttl_for_registering_the_file_upload_as_jsonld, headers={"Content-Type": "application/ld+json"})
  return response

def turtle_to_jsonld(turtle_data):
  """
    transforms RDF Turtle data to JSON-LD
  """
  graph = Graph()
  graph.parse(data=turtle_data, format="turtle")
  return graph.serialize(format="json-ld", indent=2)

def start_module(experiment_resource):
  """
    creates a message for starting a module instance
    
    be aware that http://example.org/UvA/parameters/urls_to_process is a hard-coded parameter for the module expressing the property for the input data (JSON file)
  """
  start_module_message = """
@prefix enexa:  <http://w3id.org/dice-research/enexa/ontology#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix hobbit: <http://w3id.org/hobbit/vocab#> . 
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
hobbit:instanceOf <http://w3id.org/enexa/vocab#enexa-extraction-module> ;
<http://example.org/UvA/parameters/urls_to_process> <{}> .
""".format(experiment_resource, file_id)            
  start_module_message_as_jsonld = turtle_to_jsonld(start_module_message)

  with st.expander("Now, the ENEXA task will be started at the ENEXA platform using the following message."):
    st.code(start_module_message, language="turtle")
    st.code(start_module_message_as_jsonld, language="json")

  start_container_endpoint = SERVER_ENDPOINT + "/start-container"
  response_start_module = requests.post(start_container_endpoint, data=start_module_message_as_jsonld, headers={"Content-Type": "application/ld+json"})
  return response_start_module

def get_module_instance_status_message(experiment_resource):
  """ 
    returns the message for checking the status of the module instance
  """
  check_module_instance_status_message = """
[] rdf:type enexa:ModuleInstance ;
enexa:experiment <{}> ;
""".format(experiment_resource)
  check_module_instance_status_message_as_jsonld = turtle_to_jsonld(check_module_instance_status_message)
  
  with st.expander("Check status of the module instance every {} seconds.".format(SLEEP_IN_SECONDS)):
    st.code(check_module_instance_status_message, language="turtle")
    st.code(check_module_instance_status_message_as_jsonld, language="json")
  
  return check_module_instance_status_message_as_jsonld

st.title("ENEXA Integration Demo")

st.markdown(    
"""
This demo is showing the integration of the processing steps regarding the Class Expression Learning in ENEXA.

## Knowledge Extraction 

### Input: Upload JSON files with URLs for the knowledge extraction

Upload a JSON file containing one array of URLs to Wikipedia articles.

""")
uploaded_files = st.file_uploader("Upload a JSON file", accept_multiple_files=True, label_visibility="collapsed", type=["json"])

if uploaded_files is not None and uploaded_files != []:
    for uploaded_file in uploaded_files:
        
        # create empty experiment instance
        experiment_data = create_experiment_data()
        experiment_resource = experiment_data["experiment_iri"]
        experiment_directory = experiment_data["experiment_folder"]
        relative_file_location_inside_enexa_dir = ENEXA_SHARED_DIRECTORY + "/" + experiment_directory

        uploaded_filename = uploaded_file.name.replace(" ", "_")
        uploaded_file_content = uploaded_file.read()
        
        # UI file upload
        write_file_to_folder(ENEXA_WRITEABLE_DIRECTORY, uploaded_filename, uploaded_file_content)
        st.info("File {} uploaded successfully and stored in experiment's directory: {}".format(uploaded_filename, ENEXA_WRITEABLE_DIRECTORY))

        # send configuration file to ENEXA service
        response_configuration_file_upload = configuration_file_upload(experiment_resource, relative_file_location_inside_enexa_dir, uploaded_filename)
        if response_configuration_file_upload.status_code == 200:
            st.success("ENEXA configuration file upload registered successfully.")
            st.code(pprint.pformat(response_configuration_file_upload.json(), indent=2), language="json")
            file_id = response_configuration_file_upload.json()["@id"]
            st.success("File ID for your ENEXA task: {}".format(file_id))
            
            # start a module (i.e., a new container instance of the demanded experiment will be started)
            response_start_module = start_module(experiment_resource)                    
            if response_start_module.status_code != 200:
              st.error("Error while starting ENEXA task: {}.".format(response_start_module))
            else:
                  st.info("Now, the ENEXA task should be started at the ENEXA platform. Please check the status of your task at the ENEXA platform. Request to {} done.".format(start_container_endpoint))
                  st.code(pprint.pformat(response_start_module.json(), indent=2), language="json")
                  module_instance_id = response_start_module.json()["@id"]
                  
                  check_module_instance_status_message_as_jsonld = get_module_instance_status_message(experiment_resource)
                  
                  # ask for status of the module instance until it is finished
                  while response_check_module_instance_status.status_code != 200:
                    # TODO: check endpoint
                    response_check_module_instance_status = requests.post(SERVER_ENDPOINT + "/container-status", data=check_module_instance_status_message_as_jsonld, headers={"Content-Type": "application/ld+json"})
                    time.sleep(SLEEP_IN_SECONDS)    
                    st.info("Waiting for result ({} sec) ... (TODO)".format(SLEEP_IN_SECONDS))
            
                  st.success("Module instance ({}) for the experiment ({}) finished successfully.".format(module_instance_id, experiment_resource))
        else:
            st.error("Error while registering ENEXA configuration file upload.")
            st.error(response_configuration_file_upload) 

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

