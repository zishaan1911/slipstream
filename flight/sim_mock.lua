--[[
  Mock of the ArduPilot scripting API that knife_edge.lua uses, bound to the SlipStream simulator.
  Runs in the browser (fengari, Lua 5.3) via __SS.luaRun(); the JS side is window.__AP in slipstream.html.
  World frame NED from the EKF origin, body frame FRD, as on the autopilot. Motor outputs 0-3 are M1-M4,
  output 4 is Scripting1 (fold servos). The script is scheduled like ArduPilot's: its update function runs again
  after the delay it returns, on the simulator's clock.
]]
local js = require 'js'
local AP = js.global.__AP
local PREFIX = {}

local V = {}; V.__index = V
function Vector3f(x, y, z) return setmetatable({ _x = x or 0, _y = y or 0, _z = z or 0 }, V) end
function V:x(v) if v ~= nil then self._x = v else return self._x end end
function V:y(v) if v ~= nil then self._y = v else return self._y end end
function V:z(v) if v ~= nil then self._z = v else return self._z end end
function V:length() return math.sqrt(self._x * self._x + self._y * self._y + self._z * self._z) end

local U = {}; U.__index = U
function U:tofloat() return self.v end
function U:toint() return math.floor(self.v) end
function millis() return setmetatable({ v = AP:millis() }, U) end
function micros() return setmetatable({ v = AP:millis() * 1000 }, U) end

ahrs = {}
function ahrs:get_roll_rad() return AP:att(0) end
function ahrs:get_pitch_rad() return AP:att(1) end
function ahrs:get_yaw_rad() return AP:att(2) end
ahrs.get_roll, ahrs.get_pitch, ahrs.get_yaw = ahrs.get_roll_rad, ahrs.get_pitch_rad, ahrs.get_yaw_rad
function ahrs:get_gyro() return Vector3f(AP:gyro(0), AP:gyro(1), AP:gyro(2)) end
function ahrs:get_velocity_NED() return Vector3f(AP:vel(0), AP:vel(1), AP:vel(2)) end
function ahrs:get_relative_position_NED_origin() return Vector3f(AP:pos(0), AP:pos(1), AP:pos(2)) end

vehicle = {}
function vehicle:get_mode() return AP:mode() end
function vehicle:set_target_posvelaccel_NED(p, v, a) return AP:target(1, p._x, p._y, p._z, v._x, v._y, v._z, a._x, a._y, a._z) end
function vehicle:set_target_posvel_NED(p, v) return AP:target(1, p._x, p._y, p._z, v._x, v._y, v._z, 0, 0, 0) end
function vehicle:set_target_velocity_NED(v) return AP:target(0, 0, 0, 0, v._x, v._y, v._z, 0, 0, 0) end

arming = {}
function arming:is_armed() return AP:armed() end
battery = {}
function battery:voltage(instance) return AP:volt() end

SRV_Channels = {}
function SRV_Channels:find_channel(fn) local c = AP:findchan(fn); if c < 0 then return nil end; return c end
function SRV_Channels:set_output_pwm_chan_timeout(ch, pwm, ms) AP:override(ch, pwm, ms) end
function SRV_Channels:set_output_pwm(fn, pwm) AP:fnpwm(fn, pwm) end

esc_telem = {}
function esc_telem:get_rpm(instance) return AP:rpm(instance) end   -- magnitude, like bidirectional DShot telemetry

gcs = {}
function gcs:send_text(severity, text) AP:text(severity, text) end
logger = {}
function logger:write() end

local Pm = {}; Pm.__index = Pm
function Parameter(name) return setmetatable({ n = name }, Pm) end
function Pm:init(name) self.n = name; return AP:phas(name) end
function Pm:get() if AP:phas(self.n) then return AP:pget(self.n) end; return nil end
function Pm:set(v) AP:pset(self.n, v); return true end
param = {}
function param:add_table(key, prefix, n) PREFIX[key] = prefix; return true end
function param:add_param(key, i, name, default) AP:padd(PREFIX[key] .. name, default); return true end
function param:get(name) if AP:phas(name) then return AP:pget(name) end; return nil end
function param:set(name, v) AP:pset(name, v); return true end

rc = {}
local R = {}; R.__index = R
function R:get_aux_switch_pos() return AP:aux(self.o) end
function rc:find_channel_for_option(o) return setmetatable({ o = o }, R) end

-- load the flight script and schedule it on the simulator clock
local chunk = assert(load(tostring(AP.src), '=knife_edge.lua'))
local fn, delay = chunk()
local due = AP:millis() + (delay or 0)
return function(a, b)   -- called from JS: fengari passes JS `this` first, then the clock
  local now = type(b) == 'number' and b or a
  if fn and now >= due then
    local ok, f, d = pcall(fn)
    if not ok then AP:text(0, 'Lua error: ' .. tostring(f)); fn = nil; return end
    fn, due = f, now + (d or 0)
  end
end
