"""
Constants which are used to navigate Surge XT
"""
from __future__ import annotations
__all__ = ['adsr_ampeg', 'adsr_filteg', 'cg_ENV', 'cg_FILTER', 'cg_FX', 'cg_GLOBAL', 'cg_LFO', 'cg_MIX', 'cg_OSC', 'fc_dual1', 'fc_dual2', 'fc_ring', 'fc_serial1', 'fc_serial2', 'fc_serial3', 'fc_stereo', 'fc_wide', 'fm_2and3to1', 'fm_2to1', 'fm_3to2to1', 'fm_off', 'fxslot_ains1', 'fxslot_ains2', 'fxslot_bins1', 'fxslot_bins2', 'fxslot_global1', 'fxslot_global2', 'fxslot_send1', 'fxslot_send2', 'fxt_airwindows', 'fxt_chorus4', 'fxt_conditioner', 'fxt_delay', 'fxt_distortion', 'fxt_eq', 'fxt_flanger', 'fxt_freqshift', 'fxt_neuron', 'fxt_off', 'fxt_phaser', 'fxt_reverb', 'fxt_reverb2', 'fxt_ringmod', 'fxt_rotaryspeaker', 'fxt_vocoder', 'lt_envelope', 'lt_formula', 'lt_mseg', 'lt_noise', 'lt_ramp', 'lt_sine', 'lt_snh', 'lt_square', 'lt_tri', 'ms_aftertouch', 'ms_alternate_bipolar', 'ms_alternate_unipolar', 'ms_ampeg', 'ms_breath', 'ms_ctrl1', 'ms_ctrl2', 'ms_ctrl3', 'ms_ctrl4', 'ms_ctrl5', 'ms_ctrl6', 'ms_ctrl7', 'ms_ctrl8', 'ms_expression', 'ms_filtereg', 'ms_highest_key', 'ms_keytrack', 'ms_latest_key', 'ms_lfo1', 'ms_lfo2', 'ms_lfo3', 'ms_lfo4', 'ms_lfo5', 'ms_lfo6', 'ms_lowest_key', 'ms_modwheel', 'ms_pitchbend', 'ms_polyaftertouch', 'ms_random_bipolar', 'ms_random_unipolar', 'ms_releasevelocity', 'ms_slfo1', 'ms_slfo2', 'ms_slfo3', 'ms_slfo4', 'ms_slfo5', 'ms_slfo6', 'ms_sustain', 'ms_timbre', 'ms_velocity', 'ot_FM2', 'ot_FM3', 'ot_audioinput', 'ot_classic', 'ot_shnoise', 'ot_sine', 'ot_wavetable', 'ot_window', 'pm_latch', 'pm_mono', 'pm_mono_fp', 'pm_mono_st', 'pm_mono_st_fp', 'pm_poly', 'sm_chsplit', 'sm_dual', 'sm_single', 'sm_split']
adsr_ampeg: int = 0
adsr_filteg: int = 1
cg_ENV: int = 5
cg_FILTER: int = 4
cg_FX: int = 7
cg_GLOBAL: int = 0
cg_LFO: int = 6
cg_MIX: int = 3
cg_OSC: int = 2
fc_dual1: int = 3
fc_dual2: int = 4
fc_ring: int = 6
fc_serial1: int = 0
fc_serial2: int = 1
fc_serial3: int = 2
fc_stereo: int = 5
fc_wide: int = 7
fm_2and3to1: int = 3
fm_2to1: int = 1
fm_3to2to1: int = 2
fm_off: int = 0
fxslot_ains1: int = 0
fxslot_ains2: int = 1
fxslot_bins1: int = 2
fxslot_bins2: int = 3
fxslot_global1: int = 6
fxslot_global2: int = 7
fxslot_send1: int = 4
fxslot_send2: int = 5
fxt_airwindows: int = 14
fxt_chorus4: int = 9
fxt_conditioner: int = 8
fxt_delay: int = 1
fxt_distortion: int = 5
fxt_eq: int = 6
fxt_flanger: int = 12
fxt_freqshift: int = 7
fxt_neuron: int = 15
fxt_off: int = 0
fxt_phaser: int = 3
fxt_reverb: int = 2
fxt_reverb2: int = 11
fxt_ringmod: int = 13
fxt_rotaryspeaker: int = 4
fxt_vocoder: int = 10
lt_envelope: int = 6
lt_formula: int = 9
lt_mseg: int = 8
lt_noise: int = 4
lt_ramp: int = 3
lt_sine: int = 0
lt_snh: int = 5
lt_square: int = 2
lt_tri: int = 1
ms_aftertouch: int = 4
ms_alternate_bipolar: int = 33
ms_alternate_unipolar: int = 34
ms_ampeg: int = 15
ms_breath: int = 35
ms_ctrl1: int = 7
ms_ctrl2: int = 8
ms_ctrl3: int = 9
ms_ctrl4: int = 10
ms_ctrl5: int = 11
ms_ctrl6: int = 12
ms_ctrl7: int = 13
ms_ctrl8: int = 14
ms_expression: int = 36
ms_filtereg: int = 16
ms_highest_key: int = 39
ms_keytrack: int = 2
ms_latest_key: int = 40
ms_lfo1: int = 17
ms_lfo2: int = 18
ms_lfo3: int = 19
ms_lfo4: int = 20
ms_lfo5: int = 21
ms_lfo6: int = 22
ms_lowest_key: int = 38
ms_modwheel: int = 6
ms_pitchbend: int = 5
ms_polyaftertouch: int = 3
ms_random_bipolar: int = 31
ms_random_unipolar: int = 32
ms_releasevelocity: int = 30
ms_slfo1: int = 23
ms_slfo2: int = 24
ms_slfo3: int = 25
ms_slfo4: int = 26
ms_slfo5: int = 27
ms_slfo6: int = 28
ms_sustain: int = 37
ms_timbre: int = 29
ms_velocity: int = 1
ot_FM2: int = 6
ot_FM3: int = 5
ot_audioinput: int = 4
ot_classic: int = 0
ot_shnoise: int = 3
ot_sine: int = 1
ot_wavetable: int = 2
ot_window: int = 7
pm_latch: int = 5
pm_mono: int = 1
pm_mono_fp: int = 3
pm_mono_st: int = 2
pm_mono_st_fp: int = 4
pm_poly: int = 0
sm_chsplit: int = 3
sm_dual: int = 2
sm_single: int = 0
sm_split: int = 1
