#!/usr/bin/env python3

import rospy
from std_msgs.msg import Float32
from sensor_msgs.msg import LaserScan
import math
from rc_localization_odometry.msg import SensorCollect
from ackermann_msgs.msg import AckermannDrive
import math

"""
R = L / tan(steering_angle)
Circle Center = (-R, 0)

Obstacle = (rsin(theta), rcos(theta))

Angle from center to obstacle = tan(O_y / (O_x + R))
Dist from center to obstacle = sqrt((O_x + R)^2 + O_y^2)

Circum dist to obstacle = R * angle from center to obstacle
Time to hit obstacle = circum dist to obstacle / velocity

NOTE: LIDAR'S 0 is forward, and angles increment clockwise
"""

VEHICLE_LENGTH = .3
VEHICLE_WIDTH = 0.2
AUTOBRAKE_TIME = .7
AUTOBRAKE_DISTANCE = .2
MAX_VEL = 1.5
MIN_VEL = -1.5

MIN_COLLISIONS_FOR_BRAKE = 3
LIDAR_ROTATIONAL_OFFSET = math.pi
LIDAR_HORIZONTAL_OFFSET = .035 # From center of front axle

steering_angle = 0
velocity = 0
target_velocity = 0

max_brake = Float32()
min_brake = Float32()
max_brake.data = MAX_VEL
min_brake.data = -MAX_VEL

def max_velocity(dist):
    if dist < 0:
        return MAX_VEL

    if dist < AUTOBRAKE_DISTANCE:
        return 0

    return max(0, -3.5 + math.sqrt(49 + 40*dist)/2 - .2)

def autobrake_time(vel):
    return AUTOBRAKE_TIME + vel * .1 + (.3 if vel > 1.8 else 0)

def check_collision(data: LaserScan):
    invert_x_flag = 1
    invert_y_flag = 1

    min_vel = MAX_VEL

    if steering_angle < 0:  # If the steering angle negative, flip all coordinates across the x-axis to keep calculations consistent
        invert_x_flag = -1

    if velocity < 0:  # If the velocity is negative, flip all coordinates across the y-axis to keep calculations consistent
        invert_y_flag = -1
        min_vel = -MIN_VEL

    turning_radius = VEHICLE_LENGTH / math.tan(invert_x_flag * steering_angle) if abs(steering_angle) > .01 else float('inf')  # Calculate turning radius

    # Calculate turning radii of inside and outside wheels
    inner_wheel_radius = turning_radius - VEHICLE_WIDTH/2
    outer_wheel_radius = turning_radius + VEHICLE_WIDTH/2

    for i in range(len(data.ranges)):
        if data.ranges[i] < data.range_min or data.ranges[i] > data.range_max:  # Ignore bad scans (outisde lidar range)
            continue

        dist_to_obstacle = float('inf')

        # X and Y coordinates of obstacle relative to vehicle
        theta = (LIDAR_ROTATIONAL_OFFSET + data.angle_min + i * data.angle_increment)
        r = data.ranges[i]
        x = invert_x_flag * (r * math.sin(theta) + LIDAR_HORIZONTAL_OFFSET)
        y = invert_y_flag * (r * math.cos(theta))

        if turning_radius == float('inf'):  # Straight line forward
            if abs(x) < VEHICLE_WIDTH/2:  # If the obstacle is within the width of the vehicle, then record dist and time to collision
                dist_to_obstacle = y  # Calculate distance to obstacle
            else:  # Otherwise, continue to next obstacle
                continue
        else:  # Curving
            radius_dist_to_obstacle = math.sqrt((x + turning_radius)**2 + y**2)  # Calculate radius from center of movement circle to obstacle

            if outer_wheel_radius < radius_dist_to_obstacle < inner_wheel_radius or inner_wheel_radius < radius_dist_to_obstacle < outer_wheel_radius:  # Check if obstacle within bounds of wheel circles
                angle_from_center_to_obstacle = math.atan2(y, turning_radius + x)  # Calculate angle from center of movement circle to obstacle

                if angle_from_center_to_obstacle < 0:
                    angle_from_center_to_obstacle += 2 * math.pi
                
                angle_from_center_to_obstacle %= 2 * math.pi

                dist_to_obstacle = turning_radius * angle_from_center_to_obstacle  # Calculate circumferential distance to obstacle
            else:
                continue

        if dist_to_obstacle >= 0:
            min_vel = min(min_vel, max_velocity(dist_to_obstacle))

    if invert_y_flag == -1:
        max_brake.data = MAX_VEL
        min_brake.data = -min_vel
    else:
        max_brake.data = min_vel
        min_brake.data = -MAX_VEL


def set_vars(data):
  global velocity
  global steering_angle

  velocity = data.velocity
  steering_angle = -data.steering_angle

def set_targets(data):
  global target_velocity

  target_velocity = data.speed


if __name__ == '__main__':
    rospy.init_node('autobrake')

    sub_scan = rospy.Subscriber('scan', LaserScan, check_collision)
    sub_sensor = rospy.Subscriber('sensor_collect', SensorCollect, set_vars)
    sub_movement = rospy.Subscriber('rc_movement_msg', AckermannDrive, set_targets)

    pub_max = rospy.Publisher('auto_max_vel', Float32, queue_size=1)
    pub_min = rospy.Publisher('auto_min_vel', Float32, queue_size=1)

    rospy.loginfo("Autobrake node initialized.")

    rate = rospy.Rate(30)

    while not rospy.is_shutdown():
        pub_max.publish(max_brake)
        pub_min.publish(min_brake)
        rate.sleep()

