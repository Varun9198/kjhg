import threading

class Lock:

    read_lock = threading.Lock()
    write_lock = threading.Lock()

    readers = 0

    def acquire_read(self):
        self.read_lock.acquire()
        if self.readers == 0:
            self.write_lock.acquire()
        self.readers += 1
        self.read_lock.release()

    def release_read(self):
        self.read_lock.acquire()
        self.readers -= 1
        if self.readers == 0:
            self.write_lock.release()
        self.read_lock.release()

    def acquire_write(self):
        self.write_lock.acquire()

    def release_write(self):
        self.write_lock.release()