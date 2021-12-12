from std_msgs.msg import Float64
import rospy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
import cv2
import numpy as np
import math
import tensorflow as tf
from threading import Thread, Lock
import queue
from PIL import Image as IM


class SignDetector():

    def __init__(self, image_queue):
        self.image_queue = image_queue
        self.image_mutex = Lock()
        self.model_path = "/home/nqt/catkin_ws/src/Self-driving-car/src/Traffic.h5"
        self.sign_model = tf.keras.models.load_model(self.model_path)
        self.data = None
        self.sign_detector_thread(self.image_queue)

    def sign_detector_thread(self, image_queue):
        while True:
            image = image_queue.get()
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if image is None:
                return
            # image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # ======= Process depth image =======
            result = 0
            draw = image.copy()
            keypoints = None
            keypoints = detect_keypoints(gray_image)

            if "KeyPoint" not in str(keypoints):
                pass
            else:
                blank = np.zeros((1, 1))
                draw = cv2.drawKeypoints(draw, keypoints, blank, (0, 0, 255),
                                         cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

                for keypoint in keypoints:
                    x = keypoint.pt[0]
                    y = keypoint.pt[1]
                    center = (int(x), int(y))
                    radius = int(keypoint.size / 2)

                    # Bounding box:
                    im_height, im_width, _ = draw.shape
                    pad = int(0.4*radius)
                    tl_x = max(0, center[0] - radius - pad)
                    tl_y = max(0, center[1] - radius - pad)
                    br_x = min(im_width-1, tl_x + 2 * radius + pad)
                    br_y = min(im_height-1, tl_y + 2 * radius + pad)

                    rect = ((tl_x, tl_y), (br_x, br_y))
                    crop = image[tl_y:br_y, tl_x:br_x]
                    range_image = abs(tl_x - tl_y)

                    image_fromarray = IM.fromarray(crop, 'RGB')
                    resize_image = image_fromarray.resize((30, 30))
                    expand_input = np.expand_dims(resize_image, axis=0)
                    input_data = np.array(expand_input)
                    input_data = input_data/255

                    preds = self.sign_model.predict(input_data)
                    result = preds.argmax()

            if result == 14:
                print("Stop Sign")
                flag = 1
                cv2.rectangle(draw, rect[0], rect[1], (0, 0, 255), 2)
                draw = cv2.putText(draw, "Stop Sign", rect[0], cv2.FONT_HERSHEY_SIMPLEX,
                                   0.5, (0, 255, 0), 1, cv2.LINE_AA)
                if(perios_range_image < range_image):
                    perios_range_image = range_image
                    count = 0

            elif result == 33:
                flag = 2
                cv2.rectangle(draw, rect[0], rect[1], (0, 0, 255), 2)
                draw = cv2.putText(draw, "Turn Right Sign", rect[0], cv2.FONT_HERSHEY_SIMPLEX,
                                   0.5, (0, 255, 0), 1, cv2.LINE_AA)
                print("Turn Right Sign")
                if(perios_range_image < range_image):
                    perios_range_image = range_image
                    count = 0

            elif result == 34:
                flag = 3
                cv2.rectangle(draw, rect[0], rect[1], (0, 0, 255), 2)
                draw = cv2.putText(draw, "Turn Left Sign", rect[0], cv2.FONT_HERSHEY_SIMPLEX,
                                   0.5, (0, 255, 0), 1, cv2.LINE_AA)
                print("Turn Left Sign")
                if(perios_range_image < range_image):
                    perios_range_image = range_image
                    count = 0

            elif result == 35:
                flag = 4
                cv2.rectangle(draw, rect[0], rect[1], (0, 0, 255), 2)
                draw = cv2.putText(draw, "Go Straight Sign", rect[0], cv2.FONT_HERSHEY_SIMPLEX,
                                   0.5, (0, 255, 0), 1, cv2.LINE_AA)
                print("Go Straight Sign")

            else:
                print("No info")

            self.data = flag


def detect_keypoints(image):
    # Set our filtering parameters
    # Initialize parameter settiing using cv2.SimpleBlobDetector
    params = cv2.SimpleBlobDetector_Params()

    # Set Area filtering parameters
    params.filterByArea = True
    params.minArea = 100

    # Set Circularity filtering parameters
    params.filterByCircularity = True
    params.minCircularity = 0.87

    # Set Convexity filtering parameters
    params.filterByConvexity = True
    params.minConvexity = 0.02

    # Set inertia filtering parameters
    params.filterByInertia = True
    params.minInertiaRatio = 0.01

    # Create a detector with the parameters
    detector = cv2.SimpleBlobDetector_create(params)

    # Detect blobs
    keypoints = detector.detect(image)

    return keypoints


_SHOW_IMAGE = False


class LaneDetector():
    def __init__(self):
        self.curr_steering_angle = 90
        self.line = 0

    def follow_lane(self, frame):
        # Main entry point of the lane follower
        show_image("orig", frame)

        lane_lines, frame = detect_lane(frame)
        self.line = len(lane_lines)
        final_frame = self.steer(frame, lane_lines)

        return final_frame

    def steer(self, frame, lane_lines):
        if len(lane_lines) == 0:
            return frame
        self.curr_steering_angle = compute_steering_angle(frame, lane_lines)
        # new_steering_angle = compute_steering_angle(frame, lane_lines)
        # self.curr_steering_angle = stabilize_steering_angle(
        #     self.curr_steering_angle, new_steering_angle, len(lane_lines))

        curr_heading_image = display_heading_line(
            frame, self.curr_steering_angle)
        show_image("heading", curr_heading_image)

        return curr_heading_image


def detect_lane(frame):
    edges = detect_edges(frame)
    show_image('edges', edges)

    cropped_edges = region_of_interest(edges)
    show_image('edges cropped', cropped_edges)

    line_segments = detect_line_segments(cropped_edges)
    line_segment_image = display_lines(frame, line_segments)
    show_image("line segments", line_segment_image)

    lane_lines = average_slope_intercept(frame, line_segments)
    lane_lines_image = display_lines(frame, lane_lines)
    show_image("lane lines", lane_lines_image)

    return lane_lines, lane_lines_image


def detect_edges(frame):
    # Color space conversion
    img_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    img_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HLS)

    # Detecting yellow and white colors
    low_yellow = np.array([20, 100, 100])
    high_yellow = np.array([30, 255, 255])
    mask_yellow = cv2.inRange(img_hsv, low_yellow, high_yellow)
    mask_white = cv2.inRange(img_gray, 200, 255)

    mask_yw = cv2.bitwise_or(mask_yellow, mask_white)
    mask = cv2.bitwise_and(img_gray, mask_yw)

    # detect edges
    edges = cv2.Canny(mask, 200, 400)

    return edges


def region_of_interest(canny):
    ysize = canny.shape[0]
    xsize = canny.shape[1]
    # Smoothing for removing noise
    gray_blur = cv2.GaussianBlur(canny, (5, 5), 0)

    # Region of Interest Extraction
    mask_roi = np.zeros_like(gray_blur)
    left_bottom = [0, ysize]
    right_bottom = [xsize, ysize]
    apex_left = [(0), (3*ysize/4)]
    apex_right = [(xsize), (3*ysize/4)]
    mask_color = 255
    roi_corners = np.array(
        [[left_bottom, apex_left, apex_right, right_bottom]], dtype=np.int32)
    cv2.fillPoly(mask_roi, roi_corners, mask_color)
    masked_image = cv2.bitwise_and(gray_blur, mask_roi)

    return masked_image


def detect_line_segments(cropped_edges):
    # tuning min_threshold, minLineLength, maxLineGap is a trial and error process by hand
    rho = 1  # precision in pixel, i.e. 1 pixel
    angle = np.pi / 180  # degree in radian, i.e. 1 degree
    min_threshold = 10  # minimal of votes
    line_segments = cv2.HoughLinesP(cropped_edges, rho, angle, min_threshold, np.array([]), minLineLength=10,
                                    maxLineGap=4)

    return line_segments


def average_slope_intercept(frame, line_segments):
    """
    This function combines line segments into one or two lane lines
    If all line slopes are < 0: then we only have detected left lane
    If all line slopes are > 0: then we only have detected right lane
    """
    lane_lines = []
    if line_segments is None:
        return lane_lines

    height, width, _ = frame.shape
    left_fit = []
    right_fit = []

    boundary = 1/3
    # boundary = 1/2
    # left lane line segment should be on left 2/3 of the screen
    left_region_boundary = width * (1 - boundary)
    # right lane line segment should be on left 1/3 of the screen
    right_region_boundary = width * boundary

    for line_segment in line_segments:
        for x1, y1, x2, y2 in line_segment:
            if x1 == x2:
                continue
            fit = np.polyfit((x1, x2), (y1, y2), 1)
            slope = fit[0]
            intercept = fit[1]
            if slope < 0:
                if x1 < left_region_boundary and x2 < left_region_boundary:
                    left_fit.append((slope, intercept))
            else:
                if x1 > right_region_boundary and x2 > right_region_boundary:
                    right_fit.append((slope, intercept))

    left_fit_average = np.average(left_fit, axis=0)
    if len(left_fit) > 0:
        lane_lines.append(make_points(frame, left_fit_average))

    right_fit_average = np.average(right_fit, axis=0)
    if len(right_fit) > 0:
        lane_lines.append(make_points(frame, right_fit_average))

    return lane_lines


def compute_steering_angle(frame, lane_lines):
    """ Find the steering angle based on lane line coordinate
        We assume that camera is calibrated to point to dead center
    """
    if len(lane_lines) == 0:
        return -90

    height, width, _ = frame.shape
    if len(lane_lines) == 1:
        x1, _, x2, _ = lane_lines[0][0]
        x_offset = x2 - x1
    else:
        _, _, left_x2, _ = lane_lines[0][0]
        _, _, right_x2, _ = lane_lines[1][0]
        # 0.0 means car pointing to center, -0.03: car is centered to left, +0.03 means car pointing to right
        camera_mid_offset_percent = 0.02
        mid = int(width / 2 * (1 + camera_mid_offset_percent))
        x_offset = (left_x2 + right_x2) / 2 - mid

    # find the steering angle, which is angle between navigation direction to end of center line
    y_offset = int(3*height / 4)

    # angle (in radian) to center vertical line
    angle_to_mid_radian = math.atan(x_offset / y_offset)
    # angle (in degrees) to center vertical line
    angle_to_mid_deg = int(angle_to_mid_radian * 180.0 / math.pi*0.6)
    # this is the steering angle needed by picar front wheel
    steering_angle = angle_to_mid_deg + 90

    return steering_angle


# def stabilize_steering_angle(curr_steering_angle, new_steering_angle, num_of_lane_lines, max_angle_deviation_two_lines=5, max_angle_deviation_one_lane=1):
#     """
#     Using last steering angle to stabilize the steering angle
#     This can be improved to use last N angles, etc
#     if new angle is too different from current angle, only turn by max_angle_deviation degrees
#     """
#     if num_of_lane_lines == 2:
#         # if both lane lines detected, then we can deviate more
#         max_angle_deviation = max_angle_deviation_two_lines
#     else:
#         # if only one lane detected, don't deviate too much
#         max_angle_deviation = max_angle_deviation_one_lane

#     angle_deviation = new_steering_angle - curr_steering_angle
#     if abs(angle_deviation) > max_angle_deviation:
#         stabilized_steering_angle = int(curr_steering_angle
#                                         + max_angle_deviation * angle_deviation / abs(angle_deviation))
#     else:
#         stabilized_steering_angle = new_steering_angle

#     return stabilized_steering_angle


def display_lines(frame, lines, line_color=(0, 255, 0), line_width=8, line_hight=4):
    line_image = np.zeros_like(frame)
    if lines is not None:
        for line in lines:
            for x1, y1, x2, y2 in line:
                cv2.line(line_image, (x1, y1), (x2, y2),
                         line_color, line_width, line_hight)
    line_image = cv2.addWeighted(frame, 0.8, line_image, 1, 1)
    return line_image


def display_heading_line(frame, steering_angle, line_color=(0, 0, 255), line_width=5, ):
    heading_image = np.zeros_like(frame)
    height, width, _ = frame.shape

    # figure out the heading line from steering angle
    # heading line (x1,y1) is always center bottom of the screen
    # (x2, y2) requires a bit of trigonometry

    # Note: the steering angle of:
    # 0-89 degree: turn left
    # 90 degree: going straight
    # 91-180 degree: turn right
    steering_angle_radian = steering_angle / 180.0 * math.pi
    x1 = int(width / 2)
    y1 = height
    x2 = int(x1 - 2*height / 3 / math.tan(steering_angle_radian))
    y2 = int(3*height / 4)

    cv2.line(heading_image, (x1, y1), (x2, y2), line_color, line_width)
    heading_image = cv2.addWeighted(frame, 0.8, heading_image, 1, 1)

    return heading_image


def length_of_line_segment(line):
    x1, y1, x2, y2 = line
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def show_image(title, frame, show=_SHOW_IMAGE):
    if show:
        cv2.imshow(title, frame)
        # cv2.waitKey(0)


def make_points(frame, line):
    height, width, _ = frame.shape
    slope, intercept = line
    y1 = height  # bottom of the frame
    y2 = int(y1 * 3 / 4)  # make points from middle of the frame down

    # bound the coordinates within the frame
    x1 = max(-width, min(2 * width, int((y1 - intercept) / slope)))
    x2 = max(-width, min(2 * width, int((y2 - intercept) / slope)))
    return [[x1, y1, x2, y2]]


cv_bridge = CvBridge()

velocity_pub = rospy.Publisher(
    '/autoware_gazebo/velocity', Float64, queue_size=10)
steeting_angle_pub = rospy.Publisher(
    '/autoware_gazebo/steering_angle', Float64, queue_size=10)

steeting_angle = []
element = 0
count = 0
element1 = 0
count1 = 0
angle_rad = 0


def lane_callback(data):
    global velocity_pub, steeting_angle_pub, element, count, element1, count1, angle_rad
    try:
        land_follower = LaneDetector()
        frame = cv_bridge.imgmsg_to_cv2(data, "bgr8")
        combo_image = land_follower.follow_lane(frame)

        steeting_angle.append(land_follower.curr_steering_angle)

        if(land_follower.line == 2):
            velocity_pub.publish(Float64(5))
        elif(land_follower.line == 1):
            velocity_pub.publish(Float64(2))
            if(angle_rad > 0):
                steeting_angle_pub.publish(Float64(angle_rad + 0.1))
            else:
                steeting_angle_pub.publish(Float64(angle_rad - 0.1))
        else:
            velocity_pub.publish(Float64(0))

        if(len(steeting_angle) == 15):
            data = np.average(steeting_angle, axis=None)
            angle_rad = (90 - data)/180 * math.pi * 1.2

            steeting_angle_pub.publish(Float64(angle_rad))
            print("steering angle is: ", data, angle_rad, land_follower.line)
            steeting_angle.clear()

        cv2.imshow('final', combo_image)
        cv2.waitKey(2)

    except CvBridgeError as e:
        print(e)

def sign_callback(data):
    try:
        frame = cv_bridge.imgmsg_to_cv2(data, "bgr8")
        
    except CvBridgeError as e:
        print(e)

def main():
    global rate, velocity_pub
    rospy.init_node('control', anonymous=True)
    rate = rospy.Rate(10)

    lane_sub = rospy.Subscriber(
        "/image_raw", Image, lane_callback, queue_size=1)
    sign_sub = rospy.Subscriber(
        "/image_raw", Image, sign_callback, queue_size=1)

    rospy.spin()


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down")
