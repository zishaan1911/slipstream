--[[
  Gannet SX-01 frame: a quad X on ArduPilot's 6DoF scripting mixer with all four motors reversible.

  Copter's normal mixers assume forward-only motors. With DShot ESCs in 3D (bidirectional) mode a PWM of 1000 means
  full REVERSE, so the standard quad mixer would spin the props backwards at idle. The 6DoF scripting mixer
  (FRAME_CLASS 16) is the supported way to fly reversible motors on Copter: it centres reversible outputs on 1500
  (stopped) and mixes signed thrust. knife_edge.lua takes the four outputs directly only during the knife-edge.

  Needs: FRAME_CLASS 16, SCR_ENABLE 1, DShot with SERVO_BLH_3DMASK = 15 (outputs 1-4), see gannet.parm.
  Motor order (ArduPilot quad X):  M1 front-right (CCW)   M2 rear-left (CCW)   M3 front-left (CW)   M4 rear-right (CW)
]]

-- add_motor(motor_num, roll, pitch, yaw, throttle, forward, right, reversible, testing_order)
-- factors from the arm geometry with the arms open (45 deg); roll and pitch normalised to 0.5
Motors_6DoF:add_motor(0, -0.5,  0.5,  0.5, 1, 0, 0, true, 1)   -- M1 front-right
Motors_6DoF:add_motor(1,  0.5, -0.5,  0.5, 1, 0, 0, true, 3)   -- M2 rear-left
Motors_6DoF:add_motor(2,  0.5,  0.5, -0.5, 1, 0, 0, true, 4)   -- M3 front-left
Motors_6DoF:add_motor(3, -0.5, -0.5, -0.5, 1, 0, 0, true, 2)   -- M4 rear-right

assert(Motors_6DoF:init(4), 'Gannet: unable to set up 4 reversible motors')
motors:set_frame_string('Gannet SX-01 reversible quad')
