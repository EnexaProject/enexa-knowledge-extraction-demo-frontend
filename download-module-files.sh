[ -d modules ] || mkdir -p modules
# Extraction module
curl -o modules/extraction.ttl https://raw.githubusercontent.com/EnexaProject/enexa-extraction-module/main/module.ttl
# KG Repair module
curl -o modules/repair.ttl https://raw.githubusercontent.com/EnexaProject/enexa-kg-fixing-module/master/module.ttl
# Wikidata preprocessing module
curl -o modules/wikidata-preproc.ttl https://raw.githubusercontent.com/EnexaProject/enexa-wikidata-preprocess-module/main/module.ttl
# Transformation module
curl -o modules/transform.ttl https://raw.githubusercontent.com/EnexaProject/enexa-transform-module/main/module.ttl
# Tentris service
# TODO curl -o modules/tentris.ttl 
# DICE Embeddings module
curl -o modules/embeddings.ttl https://raw.githubusercontent.com/EnexaProject/enexa-dice-embeddings/master/module.ttl
# CEL Train module
curl -o modules/cel-train.ttl https://raw.githubusercontent.com/EnexaProject/enexa-cel-train-module/main/module.ttl
# CEL service
curl -o modules/cel-deploy.ttl https://raw.githubusercontent.com/EnexaProject/enexa-cel-deploy-module/main/module.ttl
