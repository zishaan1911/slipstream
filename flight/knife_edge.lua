--[[
  Gannet SX-01: autonomous knife-edge through a slot narrower than the folded span.

    POP       short climb (~1.4 g) so the unpowered coast peaks inside the slot         Guided, posvelaccel
    ROLL      differential forward thrust rolls 90 deg right, collective near zero     motor outputs overridden
    STOP      all four ESCs brake the props to 0 rpm (3D mode, PWM 1500)               motor outputs overridden
    PUSHPULL  tail clear: one side forward, the other in reverse, equal thrust          motor outputs overridden
    LEVEL     outputs released, Guided arrests the drop and flies on                   Guided, velocity

  Runs on ArduCopter with the 6DoF scripting frame (gannet_frame.lua) and DShot ESCs in 3D mode (AM32 or BLHeli_32,
  "brake on stop" enabled). Armed in Guided, KNF_ENABLE = 1 and the Scripting1 RC switch (RCx_OPTION 300) high.
  Positions are NED metres from the EKF origin; the gate is the centre of the slot.

  Tuned in the SlipStream simulator, where this exact file runs against the physics (__SS.luaRun); see README.md.
  NOT FLIGHT TESTED. Bench and tethered roll-rig tests come first.
]]

local PARAM_KEY, PFX = 72, 'KNF_'
assert(param:add_table(PARAM_KEY, PFX, 60), 'KNF: could not add param table')
local idx = 0
local function P(name, default)
  idx = idx + 1
  assert(param:add_param(PARAM_KEY, idx, name, default), 'KNF: could not add ' .. name)
  local p = Parameter(); assert(p:init(PFX .. name), 'KNF: could not init ' .. name)
  return p
end

local ENABLE   = P('ENABLE', 0)
local GATE_N   = P('GATE_N', 7.0)      -- slot centre, NED from EKF origin [m]
local GATE_E   = P('GATE_E', 0.0)
local GATE_D   = P('GATE_D', -1.95)
local SPEED    = P('SPEED', 5.0)       -- approach speed [m/s], flying north
local T_ROLL   = P('T_ROLL', 0.30)     -- roll starts this long before the centre reaches the slot [s]
local T_POP    = P('T_POP', 0.80)      -- pop-up duration [s]
local POP_END  = P('POP_END', 0.06)    -- the pop ends this long before the roll: motors already throttled down [s]
local APEX     = P('APEX', -0.12)      -- apex height relative to the slot centre, before the roll [m]
local XOFF     = P('XOFF', -0.104)     -- east offset so the rolled silhouette is centred in the slot [m]
local LEAD     = P('LEAD', 0.06)       -- roll-in: look-ahead for the motors' spin-down lag [s]
local RI_K     = P('RI_K', 16.0)       -- roll-in: rate per rad of roll error [1/s]
local RI_WMAX  = P('RI_WMAX', 20.0)    -- roll-in: roll-rate cap [rad/s]
local RI_TC    = P('RI_TC', 0.05)      -- roll-in: rate time constant [s]
local RI_PRE   = P('RI_PRE', 0.0)      -- roll-in: brake all four rotors symmetrically for this long first [s]
local RI_T1    = P('RI_T1', 0.0)       -- roll-in bang-bang: push-pull for this long [s] (0 = feedback only)
local RI_T2    = P('RI_T2', 0.0)       --                    then full opposite (stopping) for this long [s]
local RI_F1    = P('RI_F1', 1.0)       --                    push strength (fraction of full)
local RI_F2    = P('RI_F2', 1.0)       --                    stop strength (fraction of full)
local BRK_TOL  = P('BRK_TOL', 4.0)     -- brake when the roll will settle within this of 90 deg [deg]
local BRK_RATE = P('BRK_RATE', 2.0)    -- ... and the roll rate is below this [rad/s]
local BRK_LEAD = P('BRK_LEAD', 0.04)   -- roll-rate look-ahead while the props spin down [s]
local PP_K     = P('PP_K', 8.0)        -- push-pull: rate per rad of roll error [1/s]
local PP_LAG   = P('PP_LAG', 0.07)     -- push-pull: look-ahead for the motors' reversal lag [s]
local PP_WMAX  = P('PP_WMAX', 9.0)     -- push-pull: roll-rate cap [rad/s]
local PP_TC    = P('PP_TC', 0.05)      -- push-pull: rate time constant [s]
local LIFT     = P('LIFT', 1.5)        -- lift blended back over the last 60 deg of the roll-back (x hover)
local TAIL     = P('TAIL', 0.53)       -- centre distance past the slot for the tail to be clear [m]
local FOLD_LEAD= P('FOLD_D', 0.43)     -- fold this far (plus 0.8 s of travel) before the slot [m]
local MASS     = P('MASS', 1.40)       -- [kg]
local IXX      = P('IXX', 0.0060)      -- roll inertia, arms folded [kg m^2]
local ARM      = P('ARM', 0.109)       -- roll lever, arms folded: motor axis to centreline [m]
local TMAX     = P('TMAX', 9.0)        -- max forward thrust per motor at 16.0 V [N]
local KREV     = P('KREV', 0.55)       -- reverse thrust / forward thrust at the same |PWM|
local IDLE     = P('IDLE', 0.15)       -- minimum forward thrust per motor during the roll-in [N]
local FOLD_PWM = P('FOLD_PWM', 1900)   -- fold servos (output function Scripting1): folded
local OPEN_PWM = P('OPEN_PWM', 1100)   --                                           open
local MAX_T    = P('MAX_T', 2.5)       -- abort if overriding the motors longer than this [s]
local ST_KP    = P('ST_KP', 0.0)       -- STOP: roll hold, rate per rad of error [1/s] (0 = pure brake, props to 0 rpm)
local ST_KD    = P('ST_KD', 0.05)      -- STOP: hold, rate time constant [s]
local ST_CAP   = P('ST_CAP', 1.0)      -- STOP: hold, max thrust per motor [N], balanced: zero net force
local RMODE    = P('RMODE', 0)         -- roll control: 0 rate feedback, 1 rotor-aware bang-bang (needs ESC rpm telemetry)
local RACC     = P('RACC', 10000)       -- rotor speed slew either way [rad/s^2] (thrust stand: spin-up/brake slope)
local RBRK     = P('RBRK', 6500)       -- rotor slow-down while braking (ESC regenerative limit) [rad/s^2]
local WROT     = P('WROT', 1860)       -- rotor speed at full throttle, 16 V [rad/s]
local RMARG    = P('RMARG', 0.0)       -- aim this far past the target [deg]
local RIG      = P('RIG', 0)           -- 1: roll rig (rigs/roll_rig): switch starts ROLL at once, no approach, any mode
local RIG_STOP = P('RIG_STOP', 0.25)   -- roll rig: how long the rotors stay stopped before the push-pull [s]

local G, GUIDED, K_FOLD, MODE = 9.81, 4, 94, 'IDLE'
local ST = { IDLE = 0, APPROACH = 1, POP = 2, ROLL = 3, STOP = 4, PUSHPULL = 5, LEVEL = 6, DONE = 7, ABORT = 8 }
-- motor output channels; sides for roll: left motors (M2 rear-left, M3 front-left) raise the left side
local west, lastW, tlast, RS, RDIR = { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, nil, 'accel', nil   -- rotor-speed estimates, commanded speeds, bang-bang phase
local CH, SIDE = {}, { -1, 1, 1, -1 }   -- +1 = left side: more thrust there rolls right (positive roll)
for i = 1, 4 do CH[i] = SRV_Channels:find_channel(32 + i) end
local switch = rc:find_channel_for_option(300)
local t0, tOver = 0, 0

local function now() return millis():tofloat() * 0.001 end
local function clamp(x, a, b) if x < a then return a elseif x > b then return b end return x end
local function set_state(s) MODE = s; t0 = now(); RS = 'accel'; RDIR = nil; tlast = nil; gcs:send_text(6, 'KNF ' .. s); param:set('KNF_STATE', ST[s]) end
param:add_param(PARAM_KEY, 60, 'STATE', 0)

-- thrust [N] -> 3D-mode PWM (1500 stopped, >1500 forward, <1500 reverse); thrust ~ duty^2, max scaled by pack voltage
local function pwm_for(T)
  local v = battery:voltage(0) or 16.0
  local tmax = TMAX:get() * (v / 16.0) ^ 2
  if T >= 0 then return math.floor(1500 + 500 * math.sqrt(clamp(T / tmax, 0, 1)) + 0.5) end
  return math.floor(1500 - 500 * math.sqrt(clamp(-T / (KREV:get() * tmax), 0, 1)) + 0.5)
end
local function drive(T)   -- T[i] per motor, renewed every loop with a short timeout
  for i = 1, 4 do
    lastW[i] = (T[i] >= 0) and WROT:get() * math.sqrt(math.min(T[i] / TMAX:get(), 1))
               or -WROT:get() * math.sqrt(math.min(-T[i] / (KREV:get() * TMAX:get()), 1))   -- speed this command settles at
    if CH[i] then SRV_Channels:set_output_pwm_chan_timeout(CH[i], pwm_for(T[i]), 30) end
  end
end
local function split(collective, torque)   -- per-motor thrust for a collective [N per motor] and roll torque [N m]
  local d = torque / (4 * ARM:get())
  local T = {}
  for i = 1, 4 do T[i] = collective + SIDE[i] * d end
  return T
end

-- rotor-aware roll control: measured rotor speeds (ESC telemetry), predicted forward with a constant speed slew
local function slew(w, tgt, h, rate) local a = (rate or RACC:get()) * h; if w < tgt then return math.min(tgt, w + a) end; return math.max(tgt, w - a) end
local function rotor_speeds()   -- signed [rad/s], mean of the left pair (M2, M3) and of the right pair (M1, M4)
  -- telemetry gives the magnitude only: the sign comes from each rotor's speed estimated from the commands sent
  local tn = now(); local h = tlast and (tn - tlast) or 0; local first = tlast == nil; tlast = tn
  for i = 1, 4 do
    local r = (esc_telem:get_rpm(i - 1) or 0) * 2 * math.pi / 60
    if first then west[i] = r else
      west[i] = slew(west[i], lastW[i], h)
      if math.abs(west[i]) > 150 then west[i] = (west[i] >= 0 and 1 or -1) * r end
    end
  end
  return (west[2] + west[3]) / 2, (west[1] + west[4]) / 2
end
local function thrust_at(w) local x = w / WROT:get(); if w >= 0 then return TMAX:get() * x * x end; return -KREV:get() * TMAX:get() * x * x end
local H = 0.004
local function roll_acc(wl, wr) return 2 * ARM:get() * (thrust_at(wl) - thrust_at(wr)) / IXX:get() end
local function sim_brake(th, p, wl, wr)   -- all four braked to 0 now: roll angle and rate when the rotors have stopped
  for _ = 1, 80 do
    wl, wr = slew(wl, 0, H, RBRK:get()), slew(wr, 0, H, RBRK:get())
    p = p + roll_acc(wl, wr) * H; th = th + p * H
    if math.abs(wl) < 20 and math.abs(wr) < 20 then break end
  end
  return th, p
end
local function sim_stop(th, p, wl, wr, dir)   -- full opposite torque, then brake as soon as that leaves the roll stopped
  local wf = WROT:get()
  for _ = 1, 80 do
    local bth, bp = sim_brake(th, p, wl, wr)
    if bp * dir <= 0 then return bth end
    wl, wr = slew(wl, -dir * wf, H), slew(wr, dir * wf, H)
    p = p + roll_acc(wl, wr) * H; th = th + p * H
  end
  return th
end
-- one step of a time-optimal roll to `target` [rad]: returns per-motor thrust and true once the rotors should brake
local function bang(roll, p, target, tf, trv)
  local wl, wr = rotor_speeds()
  RDIR = RDIR or ((target > roll) and 1 or -1)   -- fixed for the whole roll
  local dir = RDIR
  if RS == 'accel' and p * dir > 0.3 then
    local th_end = sim_stop(roll, p, wl, wr, dir)
    if (th_end - target - dir * math.rad(RMARG:get())) * dir >= 0 then
      RS = 'stop'
      gcs:send_text(7, string.format('KNF counter: roll %.0f p %.1f wl %.0f wr %.0f -> %.0f', math.deg(roll), p, wl, wr, math.deg(th_end)))
    end
  end
  if RS == 'stop' then
    local bth, bp = sim_brake(roll, p, wl, wr)
    if bp * dir <= 0 then
      gcs:send_text(7, string.format('KNF brake: roll %.0f p %.1f wl %.0f wr %.0f -> %.0f p %.1f', math.deg(roll), p, wl, wr, math.deg(bth), bp))
      return nil, true
    end
  end
  local push = (RS == 'accel') and dir or -dir
  local T = {}
  for i = 1, 4 do
    local up = SIDE[i] * push > 0   -- this motor pushes its side up
    T[i] = up and tf or -trv
  end
  return T, false
end

local function fold(on) SRV_Channels:set_output_pwm(K_FOLD, on and FOLD_PWM:get() or OPEN_PWM:get()) end

local function update()
  if ENABLE:get() < 1 then return update, 50 end
  local armed, guided, rig = arming:is_armed(), vehicle:get_mode() == GUIDED, RIG:get() > 0
  local sw = switch and switch:get_aux_switch_pos() == 2
  local pos, vel = ahrs:get_relative_position_NED_origin(), ahrs:get_velocity_NED()
  if rig then pos, vel = pos or Vector3f(), vel or Vector3f() end   -- on the rig nothing translates
  if not (armed and (guided or rig) and pos and vel) then
    if MODE ~= 'IDLE' and MODE ~= 'DONE' then set_state('ABORT') end
    return update, 20
  end
  local roll, p = ahrs:get_roll_rad(), ahrs:get_gyro():x()
  local s = GATE_N:get() - pos:x()                 -- distance of the centre to the slot, along track
  if rig then s = (MODE == 'STOP' and now() - t0 > RIG_STOP:get()) and -100 or 1 end   -- rig: tail 'clear' on a timer
  local vn = math.max(vel:x(), 0.5)
  local tC = s / vn

  if MODE == 'IDLE' then
    if sw and rig then fold(true); tOver = now(); set_state('ROLL')
    elseif sw then fold(false); set_state('APPROACH') end
    return update, 20

  elseif MODE == 'APPROACH' or MODE == 'POP' then
    -- ballistic plan: the roll starts T_ROLL before the slot; the pop banks the climb rate the coast will lose
    -- the coast is ballistic from POP_END before the roll: apex at the slot; the pop before it banks the climb rate
    local tr, tp = T_ROLL:get(), T_POP:get()
    local tb = tr + POP_END:get()
    local apexD = GATE_D:get() - APEX:get()
    local aUp = G * tb / tp
    local d, vd, ad
    if tC > tb then
      local dLow = apexD + 0.5 * G * tb * tb + G * tb * tp / 2   -- NED down of the low approach line
      local u = clamp((tb + tp - tC) / tp, 0, 1)
      local tt = u * tp
      d, vd, ad = dLow - 0.5 * aUp * tt * tt, -aUp * tt, (u > 0 and u < 1) and -aUp or 0
    else
      d, vd, ad = apexD + 0.5 * G * tC * tC, -G * tC, G       -- free fall: Guided throttles the motors down
    end
    local u = (tC < tb + tp) and 1 or 0
    if MODE == 'APPROACH' and u > 0 then set_state('POP') end
    if s < FOLD_LEAD:get() + vn * 0.8 then fold(true) end
    vehicle:set_target_posvelaccel_NED(Vector3f(pos:x(), GATE_E:get() + XOFF:get(), d), Vector3f(SPEED:get(), 0, vd),
                                       Vector3f(0, 0, ad), false, 0, false, 0, false)
    if s > 0 and tC <= tr and vel:x() > 1 then tOver = now(); set_state('ROLL') end
    return update, 2

  elseif MODE == 'ROLL' or MODE == 'STOP' or MODE == 'PUSHPULL' then
    if now() - tOver > MAX_T:get() then set_state('ABORT'); return update, 2 end
    local target = (MODE == 'PUSHPULL') and 0 or math.pi / 2
    local err = target - roll
    if MODE == 'ROLL' then
      local tR, T = now() - tOver - RI_PRE:get(), nil
      local v = battery:voltage(0) or 16.0
      local tf, trv = TMAX:get() * (v / 16.0) ^ 2, KREV:get() * TMAX:get() * (v / 16.0) ^ 2
      if RMODE:get() >= 1 and tR < 0 then   -- symmetric pre-brake first: roll from low rotor speeds
        T = { 0, 0, 0, 0 }
      elseif RMODE:get() >= 1 then    -- rotor-aware time-optimal roll: brakes when the prediction says it stops at 90
        local brk; T, brk = bang(roll, p, target, tf, trv)
        if brk then set_state('STOP'); drive({ 0, 0, 0, 0 }); return update, 2 end
      elseif tR < 0 then              -- symmetric pre-brake: no roll torque from unequal spin-down
        T = { 0, 0, 0, 0 }
      elseif tR < RI_T1:get() then    -- push: left side forward, right side reverse
        local f = RI_F1:get(); T = {}; for i = 1, 4 do T[i] = SIDE[i] > 0 and f * tf or -f * trv end
      elseif tR < RI_T1:get() + RI_T2:get() then   -- and the mirror image to stop the roll at 90 deg
        local f = RI_F2:get(); T = {}; for i = 1, 4 do T[i] = SIDE[i] > 0 and -f * trv or f * tf end
      else
        local wc = clamp(RI_K:get() * (err - p * LEAD:get()), -RI_WMAX:get(), RI_WMAX:get())
        T = split(0.02 * MASS:get() * G / 4, IXX:get() * (wc - p) / RI_TC:get())
      end
      if RMODE:get() < 1 then for i = 1, 4 do T[i] = math.max(T[i], IDLE:get()) end end   -- IDLE: forward-only floor (rate mode)
      drive(T)
      if math.abs(roll + p * BRK_LEAD:get() - target) < math.rad(BRK_TOL:get()) and math.abs(p) < BRK_RATE:get() then set_state('STOP') end
      if s < -TAIL:get() then set_state('PUSHPULL') end
    elseif MODE == 'STOP' then
      if ST_KP:get() > 0 then   -- props near idle, balanced pairs trim the roll: no net thrust, roll held at 90
        local d = clamp(IXX:get() * (ST_KP:get() * err - p) / ST_KD:get() / (4 * ARM:get()), -ST_CAP:get(), ST_CAP:get())
        local T = {}; for i = 1, 4 do T[i] = SIDE[i] * d end
        drive(T)
      else
        drive({ 0, 0, 0, 0 })                                  -- 1500: ESC brakes the prop to a stop
      end
      if s < -TAIL:get() then set_state('PUSHPULL') end
    else
      if RMODE:get() >= 1 then        -- rotor-aware roll back to level, then hand to Guided
        local v = battery:voltage(0) or 16.0
        local T, brk = bang(roll, p, 0, TMAX:get() * (v / 16.0) ^ 2, KREV:get() * TMAX:get() * (v / 16.0) ^ 2)
        if brk then set_state('LEVEL') else drive(T) end
        return update, 2
      end
      local wc = clamp(PP_K:get() * (err - p * PP_LAG:get()), -PP_WMAX:get(), PP_WMAX:get())
      local v = battery:voltage(0) or 16.0
      local cap = 0.9 * KREV:get() * TMAX:get() * (v / 16.0) ^ 2
      local c = math.cos(roll)
      local lift = LIFT:get() * MASS:get() * G / 4 / math.max(c, 0.5) * clamp((c - 0.5) / 0.35, 0, 1)
      local d = clamp(IXX:get() * (wc - p) / PP_TC:get() / (4 * ARM:get()), -cap, cap)
      local T = {}
      for i = 1, 4 do T[i] = lift + SIDE[i] * d end
      drive(T)
      if c > 0.94 and math.abs(p) < 3 then set_state('LEVEL') end
    end
    return update, 2

  elseif MODE == 'LEVEL' then
    -- outputs released (their timeouts lapse); Guided arrests the drop and holds the line
    if not rig then vehicle:set_target_velocity_NED(Vector3f(SPEED:get(), 0, 0)) end
    if s < -TAIL:get() - 0.15 then fold(false) end
    if now() - t0 > 1.5 then set_state('DONE') end
    return update, 10

  elseif MODE == 'DONE' or MODE == 'ABORT' then
    if MODE == 'ABORT' and not rig then vehicle:set_target_velocity_NED(Vector3f(0, 0, 0)) end
    if not sw then set_state('IDLE') end
    return update, 50
  end
  return update, 20
end

gcs:send_text(6, 'KNF knife-edge loaded')
return update, 100
