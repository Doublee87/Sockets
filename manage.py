#!/usr/bin/env python
"""
A manage process does these following tasks:
- Start a server socket to listen for connections from compute and report 
processes.
- Send value range to check for perfect numbers when  received a request 
from a compute process.
- Send server information including perfect numbers found, number tested,
and current active compute processes.
"""
import socket, signal, sys, os
import threading
import math

# Port number where this manage process listens for client connecions
SERVER_PORT = 5555

# Number of seconds for a compute process to check for perfect numbers
JOB_DURATION = 15

# To print out verbose message
VERBOSE = True

#
# Shared variables, accessible by all threads
#
# list of perfect numbers that have been found so far
perfect_numbers = []
# the last maximum value which has been sent to compute process
testing_number = 1
# largest number has been tested for perfection
tested_number = 1
# keep track of all active compute processes by storing client address of the compute
# process and its assign job (value range to check for perfect numbers) in a dictionary
# object.
compute_processes = {}
# lock to acquire access to shared variables
lock = threading.Lock()

def verbose(msg):
    """Print the given message to standard output if verbose flag is set."""
    if VERBOSE:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()

def error(msg, terminated=False):
    """Print the error message to standard error. If *terminated* is set, exit
    with status value of 1."""
    sys.stderr.write(msg + "\n")
    if terminated: sys.exit(1)

class ClientThread(threading.Thread):
    """A thread to handle message communicating between the server and a client
    process, either "compute" or "report" process."""
    
    def __init__(self, clientsocket, clientaddress):
        threading.Thread.__init__(self)
        self.sock = clientsocket
        self.addr = clientaddress
        self.done = False
        self.is_compute_process = False
        
    def stop(self):
        """Request the thread to stop.
        Close the current socket to terminate all communication."""
        self.done = True
        try:
            if self.is_compute_process:
                self.send("T\n") # send "T" message
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except:
            pass
        
    def run(self):
        """Main routine for the thread: Read for message from client and 
        response accordingly.
        """
        try:
            while not self.done:
                # read a message from client 
                msg_type, msg_data = self.read_msg()
                
                if msg_type == 'C':
                    # assign computing job to the compute process based on
                    # its performance characteristic (FLOPS)
                    self.assign_compute_job(msg_data)
                    
                    self.is_compute_process = True
                
                elif msg_type == 'P':
                    # save a perfect number from compute process
                    self.save_result(msg_data)
                
                elif msg_type == 'Q':
                    # send server information to the report process
                    self.send_server_info()
                    
                    if msg_data == 'S':
                        # got shutdown request, send INTERUPT signal to 
                        # the current process
                        os.kill(os.getpid(), signal.SIGINT)

                    self.done = True
        
        except RuntimeError, e:
            pass
        except Exception, e:
            error("Unexpected Error: %s\n" % str(e))
        finally:
            try: self.sock.close()
            except: pass
        
        lock.acquire()
        if self.addr in compute_processes:
            del compute_processes[self.addr]
        lock.release()
        
        verbose(self.name + " terminated.")
    
    def assign_compute_job(self, flops):
        """Assign the range of values to the client to check for perfect numbers.
        The value range is assigned so that it takes the client approximately 
        15 seconds to check.
        """
        global testing_number, tested_number
        
        lock.acquire()      # acquire lock to access the shared variables
        
        current_job = compute_processes.get(self.addr, None)
        
        if current_job:
            min_value, max_value = current_job
            # save the number tested
            if max_value > tested_number:
                tested_number = max_value
                
        # compute the value range to assign to the compute process which takes
        # approximately 15 seconds (set by JOB_DURATION constanst) for the 
        # client to check
        min_value = testing_number + 1
        max_value = int(math.sqrt(JOB_DURATION * flops * 2 + min_value * min_value
                                  - 2 * min_value))
        
        testing_number = max_value # update the range for the next assignment
        
        # save the compute processes
        compute_processes[self.addr] = (min_value, max_value)
        
        lock.release()      # release lock to access the shared variables
        
        # send the job assignment to the compute process
        self.send("J%d,%d\n" % (min_value, max_value))
    
    def send_server_info(self):
        lock.acquire()      # acquire lock to access the shared variables
        
        response = "Perfect numbers: %s\nNumber tested: %d\n" % (
                    str(perfect_numbers), tested_number)
        response += "Active Compute Processes:\n"
        for clientaddress, valuerange in compute_processes:
            response += "    %s: %s\n" % (str(clientaddress), str(valuerange))
        
        lock.release()      # release lock to access the shared variables

        # send server information to the report process
        self.send(response)
    
    def save_result(self, result):
        """Save the perfect number to the found list and update the number 
        tested."""
        global tested_number
        
        lock.acquire()      # acquire lock to access the shared variables
        # save the perfect number
        perfect_numbers.append(result)
        # save the number tested
        if result > tested_number:
            tested_number = result
        lock.release()      # release lock to access the shared variables
                
    def read_msg(self):
        """Read a message from the client socket. The received message
        is a well-known message according to the specified protocol."""
        
        msg = self.receive()
        while not msg: msg = self.receive()
        
        try:
            msg_type = msg[0]
            msg_data = None
            
            if msg_type == 'C':
                # Read FLOPS
                msg_data = float(msg[1:])
                
            elif msg_type == 'P':
                # Read perfect numbers
                msg_data = int(msg[1:])
                
            elif msg_type == 'Q':
                # Read shutdown request
                msg_data = msg[1]
            
            else:
                raise Exception()
                
            return msg_type, msg_data
        
        except:
            return None, None
            
    def receive(self):
        """Receive a message from client socket. A message is a string 
        terminated by a new-line character. Return the received message
        excluding the new-line character. If the socket buffer hasn't 
        contained the whole message, return None.
        """
        
        # peek the socket buffer
        recvbuf = self.sock.recv(1024, socket.MSG_PEEK)
        if not recvbuf:
            raise RuntimeError("socket connection broken")
        
        # find the message delimiter
        end = recvbuf.find("\n")
        if end == -1:
            return None # not the whole message isn't available yet
        
        msg = recvbuf[0:end]    # save the message (excluding the "\n")
        self.sock.recv(end + 1) # discard the read buffer
        
        return msg
    
    def send(self, msg):
        """Send the given message via the client socket.
        Multiple "socket.send" may be called until the whole message is sent. 
        Reference: class mysocket, method myreceive
        http://docs.python.org/howto/sockets.html
        """
        msg_len = len(msg)
        totalsent = 0
        while totalsent < msg_len:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent

def main():
    
    try:
        # http://docs.python.org/library/socket.html#example
        # create an INET, STREAMing socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # set reused address to avoid "Address already in use" problem
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # bind the socket to listen on a predefined port on all available 
        # interfaces
        server_socket.bind(("", SERVER_PORT))
        server_socket.listen(5) # set maximum queued connectiosn to 5
    except socket.error, e:
        error("socket.error: %s\n" % e, True)
        
    def sighandler(signum, frame):
        """Handler for INTERUPT, QUIT, and HANGUP signals.
        When one of these signal is received, close the server socket
        and terminate all client threads.
        """
        #verbose("Got signal " + str(signum))
        
        verbose("Closing server socket...")
        server_socket.close()
        
        verbose("Stop all client threads...")
        for client_thread in threading.enumerate():
            if isinstance(client_thread, ClientThread):
                client_thread.stop()

        verbose("Waiting all threads terminated...")
        for client_thread in threading.enumerate():
            if client_thread != threading.current_thread():
                client_thread.join()
        
        sys.exit(0) # exit normally with status code of 0

    # setup handler for INTERUPT, QUIT, and HANGUP signals
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGQUIT, sighandler)
    signal.signal(signal.SIGHUP, sighandler)
    
    while 1: # main loop to accept client connections
        
        try:
            # accept client connections
            (clientsocket, address) = server_socket.accept()
            verbose("Client %s connected." % str(address))
            
            # start a new thread to handle client communication
            client_thread = ClientThread(clientsocket, address)
            client_thread.start()
            
        except socket.error, e:
            error("socket.error: %s\n" % e)

if __name__ == '__main__':
    main()
