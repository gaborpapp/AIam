#if (defined _WIN32)
#define PRIu64 "llu"
#else
#define __STDC_FORMAT_MACROS
#include <inttypes.h>
#endif

#include "Tracker.hpp"
#include "LucasKanade.hpp"
#include "DenseOpticalFlow.hpp"
#include <sys/time.h>
#include <stdarg.h>

#if (ONI_PLATFORM == ONI_PLATFORM_MACOSX)
#include <GLUT/glut.h>
#else
#include <GL/glut.h>
#endif

#define GL_WIN_SIZE_X	640
#define GL_WIN_SIZE_Y	480
#define TEXTURE_SIZE	512

#define DEFAULT_DISPLAY_MODE	DISPLAY_MODE_DEPTH

#define MIN_NUM_CHUNKS(data_size, chunk_size)	((((data_size)-1) / (chunk_size) + 1))
#define MIN_CHUNKS_SIZE(data_size, chunk_size)	(MIN_NUM_CHUNKS(data_size, chunk_size) * (chunk_size))

bool verbose = false;
Tracker* Tracker::self = NULL;

void log(const char *format, ...) {
  va_list args;
  if(verbose) {
    va_start(args, format);
    vfprintf(stdout, format, args);
    va_end(args);
    fflush(stdout);
  }
}

#define checkGlErrors() _checkGlErrors(__LINE__)

int _checkGlErrors(int line) {
  GLenum err;
  int numErrors = 0;
  while ((err = glGetError()) != GL_NO_ERROR) {
    printf("OpenGL error at line %d: %s\n", line, gluErrorString(err));
    numErrors++;
  }
  return numErrors;
}

Tracker::Tracker() {
  self = this;
}

Tracker::~Tracker() {
  delete[] textureMap;
  openni::OpenNI::shutdown();
}

openni::Status Tracker::init(int argc, char **argv) {
  int fps = 30;
  depthAsPoints = false;
  depthThreshold = MAX_DEPTH;

  openni::Status status = openni::OpenNI::initialize();
  if(status != openni::STATUS_OK) {
    printf("Failed to initialize OpenNI\n%s\n", openni::OpenNI::getExtendedError());
    return status;
  }

  const char* deviceUri = openni::ANY_DEVICE;
  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "-device") == 0) {
      deviceUri = argv[++i];
    }

    else if(strcmp(argv[i], "-verbose") == 0) {
      verbose = true;
    }

    else if(strcmp(argv[i], "-depth-as-points") == 0) {
      depthAsPoints = true;
    }

    else if(strcmp(argv[i], "-fps") == 0) {
      fps = atoi(argv[++i]);
    }

    else if(strcmp(argv[i], "-threshold") == 0) {
      depthThreshold = atoi(argv[++i]);
    }

    else {
      printf("failed to parse argument: %s\n", argv[i]);
      return openni::STATUS_ERROR;
    }
  }

  status = device.open(deviceUri);
  if(status != openni::STATUS_OK) {
    printf("Failed to open device\n%s\n", openni::OpenNI::getExtendedError());
    return status;
  }

  status = depthStream.create(device, openni::SENSOR_DEPTH);
  if (status == openni::STATUS_OK) {
    if(deviceUri == NULL) {
      openni::VideoMode depthMode = depthStream.getVideoMode();
      depthMode.setFps(fps);
      depthMode.setResolution(640, 480);
      depthMode.setPixelFormat(openni::PIXEL_FORMAT_DEPTH_1_MM);
      status = depthStream.setVideoMode(depthMode);
    }
    if(status == openni::STATUS_OK){
      status = depthStream.start();
      if (status != openni::STATUS_OK) {
	printf("Couldn't start depth stream:\n%s\n", openni::OpenNI::getExtendedError());
	depthStream.destroy();
      }
    }
  }
  else {
    printf("Couldn't find depth stream:\n%s\n", openni::OpenNI::getExtendedError());
  }

  width = depthStream.getVideoMode().getResolutionX();
  height = depthStream.getVideoMode().getResolutionY();
  textureMap = NULL;
  InitOpenGL(argc, argv);
  histogramEnabled = false;
  processingEnabled = true;
  processingMethod = new DenseOpticalFlow(width,
					  height,
					  depthThreshold);

  return openni::STATUS_OK;
}

void Tracker::mainLoop() {
  previousDisplayTime = 0;
  glutMainLoop();
}

openni::VideoFrameRef Tracker::getDepthFrame() {
  openni::Status status = depthStream.readFrame(&depthFrame);
  if (status != openni::STATUS_OK) {
    printf("Couldn't read depth frame:\n%s\n", openni::OpenNI::getExtendedError());
  }
  return depthFrame;
}

void Tracker::ResizedWindow(int width, int height)
{
  windowWidth = width;
  windowHeight = height;
  glViewport(0, 0, windowWidth, windowHeight);
}

void Tracker::Display()
{
  struct timeval tv;
  uint64_t currentDisplayTime, timeDiff;
  gettimeofday(&tv, NULL);
  currentDisplayTime = (uint64_t) (tv.tv_sec * 1000000 + tv.tv_usec);
  if(previousDisplayTime != 0) {
    timeDiff = currentDisplayTime - previousDisplayTime;
    log("time diff: %ld\n", timeDiff);
  }
  previousDisplayTime = currentDisplayTime;

  depthFrame = getDepthFrame();
  if(!depthFrame.isValid())
    return;

  if(processingEnabled)
    processingMethod->processDepthFrame(depthFrame);

  if(textureMap == NULL) {
    textureMapWidth = MIN_CHUNKS_SIZE(width, TEXTURE_SIZE);
    textureMapHeight = MIN_CHUNKS_SIZE(height, TEXTURE_SIZE);
    textureMap = new openni::RGB888Pixel[textureMapWidth * textureMapHeight];
  }

  glClear (GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

  glMatrixMode(GL_PROJECTION);
  glLoadIdentity();
  glOrtho(0, 1.0, 1.0, 0, -1.0, 1.0);
  glMatrixMode(GL_MODELVIEW);
  glPushMatrix();
  checkGlErrors();

  if(histogramEnabled)
    calculateHistogram();
  updateTextureMap();
  drawTextureMap();

  if(processingEnabled)
    processingMethod->render();

  glPopMatrix();
  glutSwapBuffers();

  checkGlErrors();
  log("Display done\n");
}

void Tracker::calculateHistogram() {
  const openni::DepthPixel* pDepth = (const openni::DepthPixel*)depthFrame.getData();
  memset(histogram, 0, MAX_DEPTH * sizeof(float));
  int restOfRow = depthFrame.getStrideInBytes() / sizeof(openni::DepthPixel) - width;

  unsigned int nNumberOfPoints = 0;
  for (int y = 0; y < height; ++y)
    {
      for (int x = 0; x < width; ++x, ++pDepth)
	{
	  if (*pDepth != 0 && *pDepth < depthThreshold)
	    {
	      histogram[*pDepth]++;
	      nNumberOfPoints++;
	    }
	}
      pDepth += restOfRow;
    }
  for (int nIndex=1; nIndex<MAX_DEPTH; nIndex++)
    {
      histogram[nIndex] += histogram[nIndex-1];
    }
  if (nNumberOfPoints)
    {
      for (int nIndex=1; nIndex<MAX_DEPTH; nIndex++)
	{
	  histogram[nIndex] = (256 * (1.0f - (histogram[nIndex] / nNumberOfPoints)));
	}
    }
}

void Tracker::updateTextureMap() {
  memset(textureMap, 0, textureMapWidth*textureMapHeight*sizeof(openni::RGB888Pixel));

  const openni::DepthPixel* pDepthRow = (const openni::DepthPixel*)depthFrame.getData();
  openni::RGB888Pixel* textureMapRow = textureMap + depthFrame.getCropOriginY() * textureMapWidth;
  int rowSize = depthFrame.getStrideInBytes() / sizeof(openni::DepthPixel);
  unsigned char depth_uchar;

  log("rowSize=%d height=%d width=%d\n", rowSize, height, width);
  for (int y = 0; y < height; ++y)
    {
      const openni::DepthPixel* pDepth = pDepthRow;
      openni::RGB888Pixel* pTex = textureMapRow + depthFrame.getCropOriginX();

      for (int x = 0; x < width; ++x, ++pDepth, ++pTex)
	{
	  if (*pDepth != 0 && *pDepth < depthThreshold)
	    {
	      if(histogramEnabled)
		depth_uchar = (unsigned char) histogram[*pDepth];
	      else
		depth_uchar = (unsigned char) (255 * (1 - float(*pDepth) / depthThreshold));
	      pTex->r = depth_uchar;
	      pTex->g = depth_uchar;
	      pTex->b = depth_uchar;
	    }
	}

      pDepthRow += rowSize;
      textureMapRow += textureMapWidth;
    }
  log("drew frame to texture\n");
}

void Tracker::drawTextureMap() {
  if(depthAsPoints)
    drawTextureMapAsPoints();
  else
    drawTextureMapAsTexture();
}

void Tracker::drawTextureMapAsTexture() {
  glTexParameteri(GL_TEXTURE_2D, GL_GENERATE_MIPMAP_SGIS, GL_TRUE);
  checkGlErrors();
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
  checkGlErrors();
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  checkGlErrors();
  log("glTexImage2D\n");
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, textureMapWidth, textureMapHeight, 0, GL_RGB, GL_UNSIGNED_BYTE, textureMap);
  checkGlErrors();
  log("glTexImage2D ok\n");

  // Display the OpenGL texture map
  glColor4f(1,1,1,1);

  glEnable(GL_TEXTURE_2D);
  checkGlErrors();
  glBegin(GL_QUADS);

  // upper left
  glTexCoord2f(0, 0);
  glVertex2f(0, 0);
  // upper right
  glTexCoord2f((float)width/(float)textureMapWidth, 0);
  glVertex2f(1, 0);
  // bottom right
  glTexCoord2f((float)width/(float)textureMapWidth, (float)height/(float)textureMapHeight);
  glVertex2f(1, 1);
  // bottom left
  glTexCoord2f(0, (float)height/(float)textureMapHeight);
  glVertex2f(0, 1);

  glEnd();
  glDisable(GL_TEXTURE_2D);
  checkGlErrors();
}

void Tracker::drawTextureMapAsPoints() {
  float ratioX = (float)width/(float)textureMapWidth;
  float ratioY = (float)height/(float)textureMapHeight;

  glPointSize(1.0);
  glBegin(GL_POINTS);

  openni::RGB888Pixel* textureMapRow = textureMap;
  float vx, vy;
  for(unsigned int y = 0; y < textureMapHeight; y++) {
    openni::RGB888Pixel* pTex = textureMapRow;
    vy = (float) y / textureMapHeight / ratioY;
    for(unsigned int x = 0; x < textureMapWidth; x++) {
      glColor4f((float)pTex->r / 255,
      		(float)pTex->g / 255,
      		(float)pTex->b / 255,
      		1);
      vx = (float) x / textureMapWidth / ratioX;
      glVertex2f(vx, vy);
      pTex++;
    }
    textureMapRow += textureMapWidth;
  }

  glEnd();
  checkGlErrors();
}

void Tracker::glutIdle()
{
  log("glutIdle\n");
  glutPostRedisplay();
}

void Tracker::glutReshape(int width, int height) {
  Tracker::self->ResizedWindow(width, height);
}

void Tracker::glutDisplay() {
  Tracker::self->Display();
}

void Tracker::glutKeyboard(unsigned char key, int x, int y) {
  Tracker::self->onKey(key);
}

openni::Status Tracker::InitOpenGL(int argc, char **argv)
{
  glutInit(&argc, argv);
  glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH);
  glutInitWindowSize(GL_WIN_SIZE_X, GL_WIN_SIZE_Y);
  glutCreateWindow ("Tracker");
  glutSetCursor(GLUT_CURSOR_NONE);

  InitOpenGLHooks();

  glDisable(GL_DEPTH_TEST);
  glEnable(GL_TEXTURE_2D);

  glEnableClientState(GL_VERTEX_ARRAY);
  glDisableClientState(GL_COLOR_ARRAY);

  return openni::STATUS_OK;
}

void Tracker::InitOpenGLHooks()
{
  glutKeyboardFunc(glutKeyboard);
  glutDisplayFunc(glutDisplay);
  glutIdleFunc(glutIdle);
  glutReshapeFunc(glutReshape);
}

void Tracker::onKey(unsigned char key) {
  const static unsigned char TAB = 9;

  switch(key) {
  case TAB:
    processingEnabled = !processingEnabled;
    break;

  case 'h':
    histogramEnabled = !histogramEnabled;
    break;
  }

  if(processingEnabled)
    processingMethod->onKey(key);
}

int main(int argc, char **argv) {
  Tracker tracker;
  openni::Status status = tracker.init(argc, argv);
  if (status != openni::STATUS_OK)
    return 1;
  tracker.mainLoop();
}