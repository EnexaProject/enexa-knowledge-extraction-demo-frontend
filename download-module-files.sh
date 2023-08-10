[ -d modules ] || mkdir -p modules
# Extraction module
curl -o modules/extraction.ttl https://raw.githubusercontent.com/EnexaProject/enexa-transform-module/main/module.ttl
# KG Repair module
# TODO
# Transformation module
curl -o modules/transform.ttl https://raw.githubusercontent.com/EnexaProject/enexa-extraction-module/main/module.ttl
# Tentris service
# TODO
# DICE Embeddings module
curl -o modules/embeddings.ttl https://raw.githubusercontent.com/EnexaProject/enexa-dice-embeddings/master/module.ttl
# CEL Train module
# TODO
# CEL service
# TODO
