FROM semtech/mu-python-template:latest
LABEL maintainer="robbe@robbevanherck.be"

RUN apt update && apt install -y default-jre
