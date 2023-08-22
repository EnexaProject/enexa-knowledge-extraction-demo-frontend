[ -d modules ] || mkdir -p modules
# Extraction module
curl -o modules/extraction.ttl https://raw.githubusercontent.com/EnexaProject/enexa-extraction-module/main/module.ttl
# KG Repair module
curl -o modules/repair.ttl https://raw.githubusercontent.com/EnexaProject/enexa-kg-fixing-module/master/module.ttl
# Transformation module
curl -o modules/transform.ttl https://raw.githubusercontent.com/EnexaProject/enexa-transform-module/main/module.ttl
# Tentris service
# TODO curl -o modules/tentris.ttl 
# DICE Embeddings module
curl -o modules/embeddings.ttl https://raw.githubusercontent.com/EnexaProject/enexa-dice-embeddings/master/module.ttl
# CEL Train module
# TODO curl -o modules/cel-train.ttl 
# CEL service
# TODO curl -o modules/cel-service.ttl 
