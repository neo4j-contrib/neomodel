FROM python:3.7

 # Requirements have to be pulled and installed here, otherwise caching won't work
COPY . /app

# Upgrade to latest pip
RUN pip install --upgrade pip

# Install test requirements
RUN pip install -r /app/requirements.txt

# Install NeoModel
RUN pip install /app

COPY ./entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r//' /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

