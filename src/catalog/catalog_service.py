import csv
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests
import schedule

from util.rw_lock import Lock

frontend_host = os.getenv("FRONTEND_HOST", "http://localhost:8000")

# Request handler for the catalog service
class CatalogRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    # Set headers
    def _set_headers(self, message, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(message)))
        self.end_headers()

    # Handle GET requests
    def do_GET(self):
        request_components = urlparse(self.path)
        response_data = {}
        if request_components.path.split('/')[1] == "products":
            item_name = request_components.path.split('/')[2]
            # Get read lock to read data_store
            self.server.lock.acquire_read()
            data = self.server.data_store.get(item_name)
            self.server.lock.release_read()
            if data is not None:
                response_data["data"] = data
            else:
                response_data["error"] = {
                    "code": 404,
                    "message": "Item not found."
                }
        else:
            response_data = {'error': {
                'code': 400,
                'message': 'Bad request.'
            }}
        json_data = json.dumps(response_data)
        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))

    # Handle PUT requests
    def do_PUT(self):
        request_components = urlparse(self.path)
        response_data = {}
        if request_components.path.split('/')[1] == "products":
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            body = json.loads(body.decode('utf-8'))
            item_name = body.get('name')
            buy_quantity = int(body.get('quantity'))
            # Acquire write lock to write in data_store
            self.server.lock.acquire_write()
            data = self.server.data_store.get(item_name)
            if data is not None and data['quantity'] >= buy_quantity:
                self.server.data_store[item_name]['quantity'] -= buy_quantity
                self.server.cache_invalidate(item_name)
                response_data["data"] = {
                    "statusCode": 0,
                    "msg": "Success!"
                }
            elif data is None:
                response_data["data"] = {
                    "statusCode": 1,
                    "msg": "Item not found."
                }
            else:
                response_data["data"] = {
                    "statusCode": 2,
                    "msg": "Item stock insufficient."
                }
            self.server.lock.release_write()
        else:
            response_data = {'error': {
                'code': 400,
                'message': 'Bad request.'
            }}
        json_data = json.dumps(response_data)
        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))

# Catalog service
class CatalogService(ThreadingHTTPServer):
    data_store = dict()
    lock = Lock()
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    data_file = 'data/data.csv'

    def __init__(self, address, handler) -> None:
        self.read_csv()
        # Start a thread for scheduled data dump
        thread = threading.Thread(target=self.scheduled_data_dump)
        thread.start()
        thread_restock = threading.Thread(target=self.scheduled_restock)
        thread_restock.start()
        super().__init__(address, handler)

    # Read data from CSV file
    def read_csv(self):
        with open(self.data_file, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row['name']
                self.data_store[name] = {'name': name, 'quantity': int(row['quantity']), 'price': float(row['price'])}

    # Write data to CSV file
    def write_csv(self):
        self.lock.acquire_write()
        data = [self.data_store[name] for name in self.data_store]
        self.lock.release_write()

        with open(self.data_file, 'w', newline='') as csvfile:
            fieldnames = ['name', 'quantity', 'price']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)

    def cache_invalidate(self, item_name):
        frontend_url = frontend_host + '/cache/' + item_name
        requests.delete(url=frontend_url).json()

    def restock(self):
        self.lock.acquire_write()
        for item, data in self.data_store.items():
            if int(data['quantity']) == 0:
                data['quantity'] = 100
                self.cache_invalidate(item)
        self.lock.release_write()

    # Schedule data dump at intervals
    def scheduled_data_dump(self):
        schedule.every(4).seconds.do(self.write_csv)
        while True:
            schedule.run_pending()
            time.sleep(2)

    def scheduled_restock(self):
        schedule.every(10).seconds.do(self.restock)
        while True:
            schedule.run_pending()

# Start the catalog server
def run_server(handler_class=CatalogRequestHandler, port=8001):
    server_address = ('', port)
    httpd = CatalogService(server_address, handler_class)
    print(f"Server running on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
