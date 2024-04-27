#include <ros/ros.h>
#include <rc_trajectory_follower/TrajectoryMsg.h>
#include <ackermann_msgs/AckermannDrive.h>

class TrajectoryFollower {
    private:
        rc_trajectory_follower::TrajectoryMsg last_trajectory;
    public: 
        void trajectory_callback(const rc_trajectory_follower::TrajectoryMsg& trajectory)
        {
            last_trajectory = trajectory;
        }

    ackermann_msgs::AckermannDrive calculate_setpoint()
    {
        int index = (ros::Time::now() - last_trajectory.header.stamp).toSec() / last_trajectory.dt.data;

        ackermann_msgs::AckermannDrive current;
        current.speed = last_trajectory.trajectory[index].speed.data;
        current.steering_angle = last_trajectory.trajectory[index].steering_angle.data;

        return current;
    }
};



int main(int argc, char **argv)
{
    ros::init(argc, argv, "trajectory_follower");
    ros::NodeHandle nh("~");

    TrajectoryFollower follower;
    
    ros::Publisher pub = nh.advertise<ackermann_msgs::AckermannDrive>("rc_movement_msg", 10);
    ros::Subscriber sub = nh.subscribe("trajectory_msg", 10, &TrajectoryFollower::trajectory_callback, &follower);
    

    ros::Rate rate(10.0);

    while (ros::ok())
    {
        pub.publish(follower.calculate_setpoint());
        ros::spinOnce();
        rate.sleep();
    }
}