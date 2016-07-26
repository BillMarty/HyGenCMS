# See instructions here:
# http://elinux.org/Beagleboard:Expanding_File_System_Partition_On_A_microSD
sudo fdisk /dev/mmcblk0
# In fdisk
# Delete the partition with "d"
# New primary partition with: "n p 1 ENTER ENTER"
# Write with "w"
sudo reboot

# After reboot
sudo su
resize2fs /dev/mmcblk0p1

# Check with df
df

# Usage should be near 25% now