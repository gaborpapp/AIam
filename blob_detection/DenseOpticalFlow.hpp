#ifndef _DENSE_OPTICAL_FLOW_HPP_
#define _DENSE_OPTICAL_FLOW_HPP_

#include "Tracker.hpp"
#include <opencv2/video/tracking.hpp>

using namespace cv;

class DenseOpticalFlow : public ProcessingMethod {
public:
  DenseOpticalFlow(int width, int height, int depthThreshold);
  void processDepthFrame(openni::VideoFrameRef);
  void render();
  void onKey(unsigned char key);

private:
  void renderAsGrid();
  void renderEntireFlow();

  Mat frame, previousFrame;
  Mat flow;
  openni::RGB888Pixel* textureMap;
  unsigned int textureMapWidth;
  unsigned int textureMapHeight;
  bool gridMode;
};

#endif
