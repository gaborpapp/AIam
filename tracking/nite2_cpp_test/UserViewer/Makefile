include CommonDefs.mak

BIN_DIR = Bin

INC_DIRS = \
	../Common \
	${NITE2_INCLUDE} \
	../../../External/GL \
	$(OPENNI2_INCLUDE)

SRC_FILES = *.cpp

ifeq ("$(OSTYPE)","Darwin")
	CFLAGS += -DMACOS
	LDFLAGS += -framework OpenGL -framework GLUT GLU
else
	CFLAGS += -DUNIX -DGLX_GLXEXT_LEGACY
	USED_LIBS += glut GL GLU
endif

LIB_DIRS += $(OPENNI2_REDIST) $(NITE2_REDIST)

USED_LIBS += OpenNI2 NiTE2

EXE_NAME = UserViewer

CFLAGS += -Wall

include CommonCppMakefile
