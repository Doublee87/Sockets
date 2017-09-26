#!/usr/bin/env python
"""
Connects to the manage process and query for the server information
including the perfect numbers found, the number tested, and the processes
currently computing.
"""
import sys
import socket

# port number where the manage process is listening
SERVER_PORT = 5555

def main():
    request = "0"   # request to send to the server
    
    if len(sys.argv) == 2 and sys.argv[1] == "-k":
        # check if the process is invoked with "-k" switch
        request = "S"   # send "S" to request the server to shutdown
    
    elif len(sys.argv) != 1:
        # invalid command line argument, print the error and exit
        sys.stderr.write("Invalid command line argument\n")
        sys.stderr.write("Usage: %s [-k]\n" % sys.argv[0])
        sys.exit(1)
    
    try:
        # create a socket and connect to the server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", SERVER_PORT))
        
        # send Q-message, including the shutdown request if specified
        sent = sock.send("Q%s\n" % request)
        if sent != 3:
            raise RuntimeError("socket connection broken")
        
        # receive server response and print out to standard output
        while 1:
            data = sock.recv(1024)
            if not data:
                break   # no more response
            
            # print out the response from server
            sys.stdout.write(data)
            sys.stdout.flush()
        
        sock.close()

    except socket.error, e:
        sys.stderr.write("socket.error: %s\n" % e)
        sys.exit(1)
        
    except RuntimeError, e:
        sys.stderr.write("RuntimeError: %s\n" % e)
        sys.exit(1)

if __name__ == '__main__':
    main()
