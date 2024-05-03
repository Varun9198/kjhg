import json
import random
from random import randrange
import time

import requests


def main(p=1):
    # logging.basicConfig(level=logging.DEBUG)
    session = requests.Session()

    start_time = time.time()

    # url = 'http://localhost:8000/'

    url = 'http://192.168.0.24:8000/'

    items = ['Fox', 'Python', 'Tux', 'Whale', 'Dolphin', 'Elephant', 'Dragon']

    try:
        for _ in range(50):
            item = items[randrange(len(items))]
            # print(f'get request for {item}')
            get_response = session.get(url=url + 'products/' + item).json()
            # print(get_response)
            if 'error' not in get_response.keys():
                quantity = int(get_response['data']['quantity'])
                should_order = 1 if random.random() <= p and quantity > 0 else 0

                if should_order:
                    data = {'name': item, 'quantity': 1+randrange(int(1+min(quantity * 1.1, 5)))}
                    json_data = json.dumps(data)
                    headers = {'Content-type': 'application/json'}
                    # print(f'post request created {data}')
                    post_response = session.post(url=url + 'orders', data=json_data, headers=headers).json()
                    # print(post_response)

    finally:
        session.close()
        end_time = time.time()
        print("Runtime:", end_time - start_time, "seconds")


if __name__ == "__main__":
    main()
