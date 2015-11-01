4/15/13: It has been a year since I posted this config and I am still using it to run my 2.x laser and am very satisfied with the results.

Overview
========

This is an LinuxCNC 2.5+ configuration for the Buildlog.net 2.x laser cutter.
It has the following features:

* X/Y axis for the laser gantry and carriage.  Configured for MXL belts, 400 step motors and 8x microstepping.
* W axis for the table.  Configured for 1/4" 20 TPI threaded rod driven by a 400 step motor, 8x microstepping via a 48:20 belt reduction.
* Z axis which does not move the table at all but instead activates the laser when Z<0.  This provides some "instant compatibility" with mill/router CAM.

There is some minor customization to Axis, the primary LinuxCNC GUI.  Some
of the viewing angle buttons have been eliminated and page up/down have
been shifted to the U (table) axis.

The laser has a master enable provided by M3/M4/M5 (spindle control).  When the
"spindle" is off the laser cannot fire.  This means the laser turns off when
you expect it to, such as when aborting a job.

When the laser is enabled via M3/M4 it can be fired either by digital IO or
by moving the imaginary Z axis to any negative position.  Using a high "plunge"
speed in the CAM job and a very small depth of cut (such as 0.01mm) avoids
having the laser pause when it starts and stops cuts.

Special Commands
================

Laser control
-------------

Laser firing control is on parallel port pin 17.

Set laser power with M68 E0 Qxxx where xxx is a number from 0 to 100.
It is likely that your printer port's PWM output at 100 may be *more
or less than 100% power* for your laser.  The scaling values in pwmgen
component can be adjusted to bring the pwm power values inline with the
actual milli-amp power being output from the laser power supply.  This 
power setting can generally go in the preamble of your CAM setup since
you will vary PPI/DutyCycle and speed rather than power for most cutting
jobs.

Enable the laser with M3 Sxx where the spindle speed xx is in "pulses
per mm" (or about 1/25th a PPI or "pulses per inch" setting).  M3 S0 is
equivalent to "off" (or M5) and the laser will not fire.  Based on Dirk's
research the pulse length is set (in 2x_Laser.ini) to 3ms, so you can get
continuous wave output by simply picking a high enough S value for your
feed rate that pulses happen more frequently than 3ms (e.g. S10000 is
continuous for anything faster than F2).

Enable the laser with M4 Sxx where the spindle speed xx is in 
"percent duty-cycle".  M4 S0 is equivalent to "off" (or M5) and the laser
will not fire.  The laser on pulse length is 3ms (in 2x_Laser.ini) and 
duty-cycle percent adjusts now long the laser if off.  Continuous wave 
output can be selected by S100.

If you choose direct digital control of the laser, use M65 P0 ("immediate
off") in your preamble and use M62 P0/M63 P0 to turn the laser on and off
within a sequence of G1 movements.  The M62/63 are queued with movement
while M64/65 happen immediately.

If you choose "magic Z" control of the laser simply configure your CAM
job to make very shallow (0.01mm) cuts with a very fast plunge rate and
the laser will turn on whenever the CAM job "moves the router bit down".

Chiller/Assist Air Control
--------------------------

There is a digital output on parallel port pin 1 for switching an outlet
that controls the laser coolant and the assist air.  It comes on
automatically whenever M3 (the master laser enable) is on and stays on for
20 seconds after M5 (configurable in the INI as EXTRA_CHILLER_TIME).

Blower Control
--------------

There is another digital output on parallel port pin 2.  It can be
directly controlled with M62/63/64/65 P2.  I use it to control the blower
that removes smoke from the laser.

Raster Engraving
----------------

Raster operation is done by calling raster_engrave.py to generate a g-code
file that will engrave an image.  Currently all parameters are hard coded
inside this python script.  It is really a proof of concept and is in 
desperate need of a front end gui to setup raster jobs.

The generated g-code file can be touched off and executed in LinuxCNC just
like any other job.

Installation
============

This is based on an installed copy of the LinuxCNC 2.5 Ubuntu 10.04 LTS Live CD.

Install the custom laser pulse HAL component.  The first command installs
the necessary tools in case you don't have them.  For more information see
http://wiki.linuxcnc.org/emcinfo.pl?ContributedComponents

    sudo apt-get install linuxcnc-dev build-essential
    sudo comp --install laserfreq.comp
    sudo comp --install laserraster.comp

The configuration will not work without that component installed.

Find all occurances of "/home/jvangrin/Desktop/2x_Laser" in the INI and replace
with the path to your own configuration.

Configuration
=============

You must first get LinuxCNC's realtime configuration sorted out on your hardware.
There is extensive documentation for this online based around the LinuxCNC
latency-test program:  http://wiki.linuxcnc.org/emcinfo.pl?Latency-Test

My system was able to use a [EMCMOT]BASE_PERIOD of 27000 (27us) which
(along with the microstepping setting) dictates my system's maximum velocity.
If you change SCALE or BASE_PERIOD you will need to compute new MAX_VELOCITY
settings for each axis.

If your stepper configuration does not match what is described above,
compute new values for [AXIS_0]SCALE, [AXIS_1]SCALE and [AXIS_6]SCALE
in 2x_Laser.ini.  Ignore AXIS_2, it is the imaginary Z axis.

My build resulted in a maximum travel of 285x535mm.  These are the
[AXIS_0]MAX_LIMIT and [AXIS_1]MAX_LIMIT.  Setting these correctly will keep
you from banging into the physical endstops.  The 2.x build homes in the
lower left, but you can cause LinuxCNC to automatically reposition anywhere
after homing with the [AXIS_0]HOME and [AXIS_1]HOME.

If any axis moves backwards from what you expect, modify the parport
"invert" lines in 2x_Laser.hal.  Where you see
"setp parport.0.pin-03-out-invert 1", for example, change the 1 to a 0
as needed for the pins associated with xdir, ydir, udir.

If your stepper configuration varies significantly from Bart's Pololu
board, you may need to just start by running "stepconf" to find the
several detailed parameters required of your stepper driver.  You can then
port these values into the 2x_Laser HAL file.

Acknowledgements
================

Jedediah Smith at Hacklab Toronto created an EMC2 configuration for their
laser which opened my eyes to how powerful the HAL is.  In particular the
use of halstreamer synchronized with an external script is key to the
raster implementation.

Barton Dring's buildlog.net 2.x laser is one of the best open hardware
projects on the net.  The engineering work and documentation is second to
none.  Without his work on the plans and kits I wouldn't own a laser cutter.

Dirk Van Essendelft has done numerous experiments in DIY lasercutting
which he has documented on the buildlog.net forums.  His research into the
behavior of PPI with our CO2 lasers lead to improved the performance of the
PPI implementation in this configuration.

Ben Jackson for all the original work getting a working LinuxCNC 2.x laser
config and laser frequency PPI custom HAL component.
