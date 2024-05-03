import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests
import yaml

from util import rw_lock

# Environment variables or use default values
catalog_host = os.getenv("CATALOG_HOST", "http://localhost:8001")
order_host = os.getenv("ORDER_HOST", "http://localhost:")

# Request handler for the order service
class OrderRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    # Set headers
    def _set_headers(self, message, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(message)))
        self.end_headers()

    def do_GET(self):
        request_components = urlparse(self.path)
        response = {}
        if request_components.path.split('/')[1] == "backup-copy":
            start_log = urlparse(self.path).path.split('/')[2]
            self.server.lock.acquire_read()
            with open(self.server.log_file, 'r') as file:
                order_logs = file.readlines()
            orders_after_n = []

            order_number = -1
            for order in order_logs:
                if len(order) < 2:
                    continue
                order_number = int(order.split()[1])
                if order_number > int(start_log):
                    orders_after_n.append(order.strip())

            data = '\n'.join(orders_after_n)
            response["logs"] = '\n' + data
            self.server.lock.release_read()
            if order_number != -1:
                self.server.order_count = order_number

        else:
            response['error'] = {
                'code': 400,
                'message': 'Bad request.'
            }
        json_data = json.dumps(response)
        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))


    # Handle POST requests
    def do_POST(self):
        request_components = urlparse(self.path)
        response = {}
        if request_components.path.split('/')[1] == "orders":
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            body = json.loads(body.decode('utf-8'))
            item_name = body.get('name')
            buy_quantity = int(body.get('quantity'))
            if item_name is not None:
                url = catalog_host + '/products/' + item_name
                data = {'name': item_name, 'quantity': buy_quantity}
                json_data = json.dumps(data)
                headers = {'Content-type': 'application/json'}
                # Send request to catalog service to place an order
                catalog_response = requests.put(url, data=json_data, headers=headers)
                catalog_response = catalog_response.json()['data']
                if catalog_response['statusCode'] == 0:
                    # Update order log
                    self.server.lock.acquire_write()
                    self.server.order_count += 1
                    new_order_log = f"\nOrder {self.server.order_count} placed successfully: {body}."
                    with open(self.server.log_file, 'a', newline='\n') as log_file:
                        log_file.write(new_order_log)
                    response['data'] = {'order_number': self.server.order_count}
                    self.server.lock.release_write()
                    self.log_flush(new_order_log)
                else:
                    # Handle errors from catalog service
                    response['error'] = {
                        'code': 404 if catalog_response['statusCode'] == 1 else 400,
                        'message': 'Item not found.' if catalog_response[
                                                            'statusCode'] == 1 else 'Item stock insufficient.'
                    }
            else:
                response['error'] = {
                    'code': 400,
                    'message': 'Bad request.'
                }
        elif request_components.path.split('/')[1] == "health-check":
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            body = json.loads(body.decode('utf-8'))
            if self.server.copy_flag:
                response['status'] = 'pending'
            elif body.get('leader') == '':
                response['status'] = 'running'
                self.server.leader_order_port = self.server.self_port
            elif body.get('leader') == self.server.leader_order_port:
                response['status'] = 'running'
            elif self.server.leader_order_port != '' and body.get('leader') != self.server.leader_order_port:
                self.server.leader_order_port = str(body.get('leader'))
                response['status'] = 'running'
            else:
                self.server.leader_order_port = str(body.get('leader'))
                response['status'] = 'pending'
                thread = threading.Thread(target=self.copy_log)
                thread.start()
        elif request_components.path.split('/')[1] == 'log-flush':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            body = json.loads(body.decode('utf-8'))
            new_log = body.get('log')
            self.server.lock.acquire_write()
            with open(self.server.log_file, 'a', newline='\n') as log_file:
                log_file.write(new_log)
            self.server.lock.release_write()
            self.server.order_count = max(self.server.order_count, int(new_log.strip().split()[1]))

        else:
            response['error'] = {
                'code': 400,
                'message': 'Bad request.'
            }
        json_data = json.dumps(response)
        self._set_headers(json_data)
        self.wfile.write(json_data.encode('utf-8'))

    def copy_log(self):
        self.server.copy_flag = True
        self.server.lock.acquire_read()
        with open(self.server.log_file, 'r') as log_file:
            lines = log_file.readlines()
            if lines:
                last_line = lines[-1]
                last_order_number = last_line.split()[1]
            else:
                last_order_number = 0
        self.server.lock.release_read()
        backup_logs = requests.get(url=order_host + self.server.leader_order_port +
                         '/backup-copy/' + str(last_order_number)).json()['logs']
        if len(backup_logs) > 2:
            self.server.lock.acquire_write()
            with open(self.server.log_file, 'a', newline='\n') as log_file:
                log_file.write(backup_logs)
            self.server.lock.release_write()
        self.server.copy_flag = False

    def log_flush(self, new_order_log):
        for port in self.server.other_port:
            body = json.dumps({'log': new_order_log})
            order_replica_url = order_host + str(port) + '/log-flush'
            headers = {'Content-type': 'application/json'}
            try:
                requests.post(url=order_replica_url, data=body, headers=headers)
            except:
                print(f'flush failed for replica port {port}')
                continue

# Order service
class OrderService(ThreadingHTTPServer):
    lock = rw_lock.Lock()
    order_count = 0
    leader_order_port = ''
    copy_flag = False
    def __init__(self, address, handler, self_port) -> None:
        # Initialize order count from the order log file
        self.self_port = self_port
        os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
        self.log_file = f'data/order_log_{self_port}.txt'
        with open(self.log_file, 'r') as read_file:
            lines = read_file.readlines()
            if len(lines) != 0:
                self.order_count = int(lines[-1].split()[1])
        with open(f"config/config_{self_port}.yml") as file:
            self.other_port = yaml.safe_load(file)['other_port']
        super().__init__(address, handler)

# Start the order server
def run_server(handler_class=OrderRequestHandler):
    current_port = 8002
    server_address = ('', int(current_port))
    httpd = OrderService(server_address, handler_class, current_port)
    print(f"Server running on port {current_port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
