import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests
import schedule
import yaml

from util.cache import LRUCache
from util.rw_lock import Lock

# Environment variables or use default values
catalog_host = os.getenv("CATALOG_HOST", "http://localhost:8001")
order_host = os.getenv("ORDER_HOST", "http://localhost:")

# Request handler for frontend
class FrontendRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    cache = LRUCache(2)

    order_service_port = ''

    # Set headers
    def _set_headers(self, message, status_code=200, content_type='text/html'):
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(message)))
        self.end_headers()

    # Handle GET requests
    def do_GET(self):
        request_components = urlparse(self.path)
        if request_components.path.split('/')[1] == "products":
            item_name = request_components.path.split('/')[2]

            if not self.server.use_cache:
                cache_value = -1
            else:
                cache_value = self.cache.get(item_name)

            if cache_value != -1:
                json_data = json.dumps(cache_value)
            else:
                catalog_url = catalog_host + '/products/' + item_name
                # Fetch data from the catalog service
                catalog_response = requests.get(url=catalog_url).json()
                if self.server.use_cache:
                    self.cache.put(item_name, catalog_response)
                json_data = json.dumps(catalog_response)
        else:
            # Respond with an error for other requests
            response = {'error': {
                'code': 400,
                'message': 'Bad request.'
            }}
            json_data = json.dumps(response)
        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))

    # Handle POST requests
    def do_POST(self):
        request_components = urlparse(self.path)
        if request_components.path.split('/')[1] == "orders":
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            order_url = order_host + self.server.leader + '/orders'
            headers = {'Content-type': 'application/json'}
            # Send order data to the order service
            order_response = requests.post(url=order_url, data=body, headers=headers).json()
            json_data = json.dumps(order_response)
        else:
            # Respond with an error for other requests
            response = {'error': {
                'code': 400,
                'message': 'Bad request.'
            }}
            json_data = json.dumps(response)
        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))

    def do_DELETE(self):
        request_components = urlparse(self.path)
        if request_components.path.split('/')[1] == "cache":
            item_name = request_components.path.split('/')[2]
            self.cache.delete(item_name)

        json_data = json.dumps({})

        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))

    def handle(self):
        print("Connection made from:", self.client_address)
        super().handle()


# Catalog service
class FrontendService(ThreadingHTTPServer):
    lock = Lock()
    leader = ''

    def __init__(self, address, handler, use_cache) -> None:
        # Start a thread for scheduled data dump
        self.leader_election(False)
        self.use_cache = use_cache
        thread = threading.Thread(target=self.scheduled_health_check)
        thread.start()
        super().__init__(address, handler)

    def leader_election(self, leader_up):
        with open("config.yml") as file:
            order_service_ports = yaml.safe_load(file)['order_service_ports']

        order_service_ports.sort(reverse=True)
        while not leader_up or self.leader == '':
            for order_service_port in order_service_ports:
                url = order_host + str(order_service_port) + '/health-check'
                json_data = json.dumps({'leader': ''})
                headers = {'Content-type': 'application/json'}
                try:
                    node_status = requests.post(url=url, data=json_data, headers=headers).json()['status']
                    if node_status == 'running':
                        self.leader = str(order_service_port)
                        print('Leader order port set as: ', self.leader)
                        leader_up = True
                        break
                except:
                    continue

    def health_check(self):
        with open("config.yml") as file:
            order_service_ports = yaml.safe_load(file)['order_service_ports']

        for order_service_port in order_service_ports:
            url = order_host + str(order_service_port) + '/health-check'
            json_data = json.dumps({'leader': self.leader})
            headers = {'Content-type': 'application/json'}
            try:
                node_status = requests.post(url=url, data=json_data, headers=headers).json()['status']
                if node_status != 'running':
                    raise Exception('node is not in running state')
            except:
                if str(order_service_port) == self.leader:
                    self.leader_election(False)

    # Schedule data dump at intervals
    def scheduled_health_check(self):
        schedule.every(1).seconds.do(self.health_check)
        while True:
            schedule.run_pending()


# Start the frontend server
def run(server_class=FrontendService, handler_class=FrontendRequestHandler, port=8000, use_cache=True):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class, use_cache)
    print(f"Server running on port {port}")
    httpd.serve_forever()


if __name__ == '__main__':
    run()
