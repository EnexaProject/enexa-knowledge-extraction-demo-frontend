IMAGE=hub.cs.upb.de/enexa/images/enexa-ui-demo
VERSION=1.0.0
TAG=$(IMAGE):$(VERSION)

build:
	docker build -t $(TAG) .
	
push:
	docker push $(TAG)

push-latest:
	docker tag $(TAG) $(IMAGE):latest
	docker push $(IMAGE):latest

