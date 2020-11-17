FROM alpine:3.12

RUN apk add --no-cache python3 py3-pip py3-wheel py3-requests && \
    pip install kubernetes==12.0.1 && \
    apk del py3-pip py3-wheel

ADD k8s-configmap-update.py /usr/local/bin/
RUN chmod +x /usr/local/bin/k8s-configmap-update.py
