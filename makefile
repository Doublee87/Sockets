CC = icc
CXX = icpc
CFLAGS = -Wall -std=c99 -openmp -O3
CXXFLAGS = -Wall -openmp -O3
#overkill on the flags, but that doesn't hurt anything
LDFLAGS = -lrt -lpthread 
#replace this if you want to change the output name
TARGET = compute

#any headers go here
INCLUDES = 

#any .c or .cpp files go here
SOURCE = compute.c

#default is to compile
default:compile

#depends on all of you source and header files
compile: ${SOURCE} ${INCLUDES}
#this assumes you actually are linking all of the source files together
	${CC} ${CFLAGS} ${SOURCE} -o ${TARGET} ${LDFLAGS}

debug: ${SOURCE} ${INCLUDES}
	${CC} ${CFLAGS} ${SOURCE} -o ${TARGET} ${LDFLAGS} -DDEBUG