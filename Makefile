IMAGE=hub.cs.upb.de/enexa/images/enexa-ui-demo
VERSION=1.3.0-tentris-demo
TAG=$(IMAGE):$(VERSION)

build:
	docker build -t $(TAG) .
	
push:
	docker push $(TAG)

push-latest:
	docker tag $(TAG) $(IMAGE):latest
	docker push $(IMAGE):latest

