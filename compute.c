#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/times.h>


/* Host name or IP address of the server */
#define SERVER_ADDR		"localhost"

/* Port number where the manage process is listening */
#define SERVER_PORT 	5555

/* Size of buffer to send or receive message */
#define BUFFER_SIZE     1024

/* Number of operations to compute FLOPS */
#define NUMBER_OPERATIONS	10000000

/* Thread functions */
void thread_create(pthread_t *ptid, void *(*rountine)(void *), void *argp);
int  thread_join(pthread_t tid);

/* Socket communication functions */
int sock_read_message(int sockfd, char msg_type, char *msg_data);
int sock_send_message(int sockfd, char *buffer);

/* Calculate number of floating-point operations per second (FLOPS) */
double calculate_flops();

/* Test if n is a perfect number */
int is_perfect_number(long n);

/* Timinng functions from the exampe timing.c:
http://web.engr.oregonstate.edu/cgi-bin/cgiwrap/dmcgrath/classes/12Su/cs311/
index.cgi?examples=examples/timing.c */
static int timer_set = 0;
static double old_time;
void start_timer();
double elapsed_time();
double user_time();

/* handler for INT, QUIT and HUP signals */
void signal_handler(int signum);

/* Thread to check for shut down message from server */
void *comm_thread(void *arg);

/* Print the error message and exit */
void error(char *msg);

/* Compute performance characteristics FLOPS by running a large number
of floating point add-operation and measure the time. */
double calculate_flops() {
	double flops, temp;
	int i;
	
	start_timer();
	
	temp = 0;
	for (i = 0; i < NUMBER_OPERATIONS; i++) {
		temp *= 31.23433234;
	}
	
	flops = NUMBER_OPERATIONS / elapsed_time();
	
	return flops;
}

/* Test if n is a perfect number by finding the sum of all of its proper 
divisors, start from 1 to n/2. */
int is_perfect_number(long n) {

	long i, sum = 0;
	
	for (i = 1; i <= n / 2; i++) {
		if (n % i == 0) {
			sum += i;
		}
	}

	return sum == n;
}

void *comm_thread(void *arg) {

    int sock; /* Communicating socket */
    int ret;

    /* Get socket stream from the thread argument */
    sock = *((int *) arg);
    free(arg);      /* free the argument's memory */
    
    /* Check for "T" message from server */
    while ((ret = sock_read_message(sock, 'T', NULL)) == 0);

    if (ret == -1) {
        error("socket connection broken");
    } else {
        /* Terminate the process by sending INT signal to itself */
        kill(getpid(), SIGINT);
    }

    return NULL;
}

static int sockfd;

int main(int argc, char **argv) {

	struct sockaddr_in server_addr;
	
	pthread_t tid;		/* thread's id */
	void *thread_arg;	/* To pass arguments to a thread */

    char buffer[BUFFER_SIZE];
    int ret;
    char *pos;

	long min, max;
	long n;
	
	/* Create socket to connect to the server */
	sockfd = socket(AF_INET, SOCK_STREAM, 0);
	if (sockfd < 0) {
		error("socket() error");
	}
	
	/* Setup server_addr struct */
	bzero(&server_addr, sizeof(server_addr));
	server_addr.sin_family = AF_INET;
	server_addr.sin_port = htons(SERVER_PORT);
	inet_pton(AF_INET, SERVER_ADDR, &server_addr.sin_addr);
	
	/* Connect to the server */
	if (connect(sockfd, (struct sockaddr *) &server_addr, 
			sizeof(server_addr)) < 0) {
		error("connect() error");
	}
	
	/* Register handler for INTERUPT, QUIT, and HANGUP signals */
    if (SIG_ERR == signal(SIGINT, signal_handler) ||
    		SIG_ERR == signal(SIGQUIT, signal_handler) ||
    		SIG_ERR == signal(SIGHUP, signal_handler)) {
        error("signal() error");
    }
	
    
    /* Create thread to check for "termination" request from */
    thread_arg = calloc(sizeof(int), 1);
    *((int *) thread_arg) = sockfd;
    thread_create(&tid, comm_thread, thread_arg);

	while (1) {
		
		/* Compute FLOPS to request the server for computing job */
		sprintf(buffer, "C%f\n", calculate_flops());
		
		/* Send "C" message to request the value range to check for 
		perfect numbers */
	    if (!sock_send_message(sockfd, buffer)) {
	        error("error in sending C-message");
	    }

	    /* Read "J" message from server */
	    while ((ret = sock_read_message(sockfd, 'J', buffer)) != 2) {

	        if (ret == -1) {
	            error("socket connection broken");
	        }
	        /* No message is available */
	        if (ret == 0) {
	            continue;
	        }
	    
			pos = strchr(buffer, ',');
			if (pos == NULL) {
				error("invalid message received");
			}
			
			min = atol(buffer);
			max = atol(pos + 1);
	        break;
	    }
	    
	    printf("Finding perfect numbers in range [%ld, %ld]\n", min, max);
	    
	    /* Find perfect numbers in the given range */
		for (n = min; n <= max; n++) {
			if (is_perfect_number(n)) {
				/*printf("Found %d\n", n);*/
				
				/* Send the result to the manage process */
				sprintf(buffer, "P%ld\n", n);
				if (!sock_send_message(sockfd, buffer)) {
					error("socket connection broken");
				}
			}
		}
	}

	return 0;
}

void signal_handler(int signum) {
	close(sockfd);    /* close the socket */
	exit(0);
}

/* Create a thread running the given rountine */
void thread_create(pthread_t *ptid, void *(*rountine)(void *), void *argp) {

    pthread_attr_t attr;
    int ret;

    /* Set thread as detached */
    pthread_attr_init(&attr);
	if (0 != pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED)) {
		error("thread_create() error");
	}

    ret = pthread_create(ptid, &attr, rountine, argp);
    if (ret != 0) {
        error("pthread_create() error");
    }

    pthread_attr_destroy(&attr);
}

int thread_join(pthread_t tid) {
    void *status;
    int ret;

    ret = pthread_join(tid, &status);
    if (ret != 0) {
        error("pthread_join() error");
    }

    return (long) status;
}

/* Read a message which is a string terminated by a new-line character
 * from the given socket.
 */
int sock_read_message(int sockfd, char msg_type, char *msg_data) {

	char buffer[BUFFER_SIZE];
	
    int nRead;
    char *pos;

    bzero(buffer, BUFFER_SIZE);
    nRead = recv(sockfd, buffer, BUFFER_SIZE - 1, MSG_PEEK);
    if (nRead < 0) {
        return -1; /* Error */
    }
    if (nRead == 0) {
        return 2; /* Socket closed */
    }

    /* Find \n in the buffer */
    pos = strchr(buffer, '\n');
    if (pos == NULL) {
        return 0;   /* No message available yet */
    }
    
    /* check for message type */
    if (buffer[0] != msg_type) {
    	return 0;	 /* The request message is not available yet */
    }

    bzero(buffer, BUFFER_SIZE);
    nRead = recv(sockfd, buffer, pos - buffer + 1, 0);
    if (nRead <= 0) {
        return -1;
    }
    
    if (msg_data != NULL) {
    	strcpy(msg_data, buffer + 1);
    }
    
    return 1;
}

int sock_send_message(int sockfd, char *buffer) {
	int len = strlen(buffer);
    return send(sockfd, buffer, len, 0) == len;
}

/* Return the amount of time in seconds used by the current process since
   it began. */
double  user_time () 
{
	struct rusage   t;

	/* Get resource usage from system */
	if (getrusage(RUSAGE_SELF, &t)) {
		error("getrusage failure");
	}
	
	/* Return processes user mode time in seconds. */
	return (t.ru_utime.tv_sec + (t.ru_utime.tv_usec / 1.0e6));
}

/* Starts timer. */
void start_timer () 
{
	timer_set = 1;
	old_time = user_time ();
}

/* Returns elapsed time since last call to start_timer().  Returns ERROR_VALUE
   if Start_Timer() has never been called. */
double  elapsed_time () 
{
	if (!timer_set) {
		return (-1);
	} else {
		return (user_time () - old_time);
	}
}

/* Print the error and then exit */
void error(char *msg) {
    perror(msg);
    exit(1);
}

