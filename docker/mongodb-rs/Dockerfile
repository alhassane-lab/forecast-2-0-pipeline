FROM mongo:6.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates jq \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
