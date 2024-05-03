from collections import OrderedDict
from util.rw_lock import Lock


class LRUCache:

    def __init__(self, capacity):
        self.data = OrderedDict()
        self.capacity = capacity
        self.lock = Lock()

    def get(self, key):
        ans = -1
        if key in self.data:
            self.lock.acquire_write()
            ans = self.data.setdefault(key, self.data.pop(key))
            self.lock.release_write()
        print('get: ', self.data.keys())
        return ans

    def put(self, key, value):
        self.lock.acquire_write()
        if key not in self.data.keys():
            self.data[key] = value
            if len(self.data) > self.capacity:
                self.data.popitem(last=False)
        else:
            self.data.move_to_end(key)
            self.data[key] = value
        print('put: ', self.data.keys())
        self.lock.release_write()

    def delete(self, key):
        if key in self.data.keys():
            self.lock.acquire_write()
            self.data.pop(key)
            self.lock.release_write()
        print('del: ', self.data.keys())
