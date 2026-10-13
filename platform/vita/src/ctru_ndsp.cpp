// NDSP on the Vita: the 3DS DSP mixer emulated in software. Each of the 24
// channels plays its queue of wave buffers (DSP-ADPCM, PCM16, PCM8, stereo
// PCM16) at its sample rate with linear interpolation, the one-pole IIR
// low-pass, and the front left/right mix; the sum goes to the Vita's main
// audio port at 48 kHz. The DSP frame clock (160 samples at 32728 Hz) that
// paces the game's sound engine advances with the samples output.
// Semantics follow libctru's ndsp-channel.c (buffer states, reset defaults).
#include <3ds.h>
#include <psp2/audioout.h>
#include <psp2/kernel/threadmgr.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>

namespace {

constexpr int Channels = 24;
constexpr int OutputRate = 48000;
constexpr int Grain = 256; // samples per sceAudioOutOutput
constexpr double DspFrameRate = 32728.0 / 160.0;

struct Voice {
	ndspWaveBuf* head = nullptr;
	u16 format = NDSP_FORMAT_PCM16;
	float rate = 1.f;
	float mix[2] = {1.f, 1.f};
	bool paused = false;
	bool iir = false;
	float iirA = 1.f, iirB = 0.f, iirL = 0.f, iirR = 0.f;
	s16 coefs[16] = {};
	s16 hist1 = 0, hist2 = 0;
	u32 pos = 0;
	float frac = 0.f;
	float s0[2] = {}, s1[2] = {};
	bool primed = false;
};

LightLock lock;
Voice voices[Channels];
float masterVolume = 1.f;
bool softClip = true;
ndspCallback callback = nullptr;
void* callbackData = nullptr;
std::atomic<u32> frameCount{0};
std::atomic<bool> running{false};
SceUID thread = -1;
int port = -1;

void resetVoice(Voice& v) {
	for (ndspWaveBuf* b = v.head; b; b = b->next) b->status = NDSP_WBUF_DONE;
	v = Voice{};
}

// The voice's next source frame into out[0..1] (mono repeats left), or false
// when its queue is empty.
bool nextSample(Voice& v, float* out) {
	for (;;) {
		ndspWaveBuf* b = v.head;
		if (!b) return false;
		const u16 encoding = (v.format >> 2) & 3;
		if (b->status == NDSP_WBUF_QUEUED) {
			b->status = NDSP_WBUF_PLAYING;
			v.pos = 0;
			if (encoding == NDSP_ENCODING_ADPCM && b->adpcm_data) { v.hist1 = b->adpcm_data->history0; v.hist2 = b->adpcm_data->history1; }
		}
		if (v.pos >= b->nsamples) {
			if (b->looping) {
				v.pos = 0;
				if (encoding == NDSP_ENCODING_ADPCM && b->adpcm_data) { v.hist1 = b->adpcm_data->history0; v.hist2 = b->adpcm_data->history1; }
				if (!b->nsamples) return false;
			} else {
				b->status = NDSP_WBUF_DONE;
				v.head = b->next;
				continue;
			}
		}
		const u32 i = v.pos++;
		if (encoding == NDSP_ENCODING_ADPCM) {
			// 8-byte frames: predictor/scale header, then 14 four-bit samples.
			const u8* frame = b->data_adpcm + (i / 14) * 8;
			const unsigned n = i % 14;
			const u8 header = frame[0];
			const int scale = 1 << (header & 15), predictor = (header >> 4) & 7;
			int nibble = (frame[1 + n / 2] >> (n & 1 ? 0 : 4)) & 15;
			if (nibble >= 8) nibble -= 16;
			int sample = ((nibble * scale) << 11) + 1024 + v.coefs[predictor * 2] * v.hist1 + v.coefs[predictor * 2 + 1] * v.hist2;
			sample >>= 11;
			sample = std::clamp(sample, -32768, 32767);
			v.hist2 = v.hist1;
			v.hist1 = s16(sample);
			out[0] = out[1] = float(sample) / 32768.f;
		} else if (encoding == NDSP_ENCODING_PCM16) {
			if (NDSP_CHANNELS(v.format) == 2) {
				out[0] = float(b->data_pcm16[i * 2]) / 32768.f;
				out[1] = float(b->data_pcm16[i * 2 + 1]) / 32768.f;
			} else out[0] = out[1] = float(b->data_pcm16[i]) / 32768.f;
		} else {
			if (NDSP_CHANNELS(v.format) == 2) {
				out[0] = float(b->data_pcm8[i * 2]) / 128.f;
				out[1] = float(b->data_pcm8[i * 2 + 1]) / 128.f;
			} else out[0] = out[1] = float(b->data_pcm8[i]) / 128.f;
		}
		return true;
	}
}

void mix(float* out, int samples) {
	std::fill(out, out + samples * 2, 0.f);
	LightLock_Lock(&lock);
	for (Voice& v : voices) {
		if (v.paused || (!v.head && !v.primed)) continue;
		const float step = v.rate / float(OutputRate);
		if (!v.primed) {
			float s[2];
			if (!nextSample(v, s)) continue;
			v.s0[0] = v.s1[0] = s[0];
			v.s0[1] = v.s1[1] = s[1];
			v.frac = 0.f;
			v.primed = true;
		}
		for (int i = 0; i < samples; ++i) {
			float l = v.s0[0] + (v.s1[0] - v.s0[0]) * v.frac;
			float r = v.s0[1] + (v.s1[1] - v.s0[1]) * v.frac;
			if (v.iir) {
				v.iirL = v.iirA * l + v.iirB * v.iirL;
				v.iirR = v.iirA * r + v.iirB * v.iirR;
				l = v.iirL; r = v.iirR;
			}
			out[i * 2] += l * v.mix[0];
			out[i * 2 + 1] += r * v.mix[1];
			v.frac += step;
			while (v.frac >= 1.f) {
				v.frac -= 1.f;
				v.s0[0] = v.s1[0]; v.s0[1] = v.s1[1];
				float s[2];
				if (nextSample(v, s)) { v.s1[0] = s[0]; v.s1[1] = s[1]; }
				else { v.s1[0] = v.s1[1] = 0.f; v.primed = false; }
			}
			if (!v.primed && !v.head) break;
		}
	}
	LightLock_Unlock(&lock);
}

int mixerThread(SceSize, void*) {
	alignas(64) static s16 buffers[2][Grain * 2];
	static float mixed[Grain * 2];
	int which = 0;
	double frames = 0;
	while (running.load(std::memory_order_acquire)) {
		mix(mixed, Grain);
		s16* out = buffers[which];
		for (int i = 0; i < Grain * 2; ++i) {
			float x = mixed[i] * masterVolume;
			if (softClip) {
				// A gentle knee above 0.8 instead of hard clipping.
				const float a = std::fabs(x);
				if (a > 0.8f) x = std::copysign(0.8f + 0.2f * std::tanh((a - 0.8f) / 0.2f), x);
			}
			out[i] = s16(std::clamp(x, -1.f, 1.f) * 32767.f);
		}
		sceAudioOutOutput(port, out);
		which ^= 1;
		// The DSP frame clock: one callback per elapsed 160-sample frame.
		frames += double(Grain) / OutputRate * DspFrameRate;
		while (frames >= 1.0) {
			frames -= 1.0;
			frameCount.fetch_add(1, std::memory_order_release);
			if (ndspCallback cb = callback) cb(callbackData);
		}
	}
	return 0;
}

} // namespace

extern "C" Result ndspInit(void) {
	if (running.load()) return 0;
	LightLock_Init(&lock);
	port = sceAudioOutOpenPort(SCE_AUDIO_OUT_PORT_TYPE_MAIN, Grain, OutputRate, SCE_AUDIO_OUT_MODE_STEREO);
	if (port < 0) return -1;
	int volume[2] = {SCE_AUDIO_VOLUME_0DB, SCE_AUDIO_VOLUME_0DB};
	sceAudioOutSetVolume(port, SceAudioOutChannelFlag(SCE_AUDIO_VOLUME_FLAG_L_CH | SCE_AUDIO_VOLUME_FLAG_R_CH), volume);
	running.store(true);
	// Highest user priority on the third core, beside the game's audio threads.
	thread = sceKernelCreateThread("mkw_ndsp", mixerThread, 64, 0x10000, 0, SCE_KERNEL_CPU_MASK_USER_2, nullptr);
	if (thread < 0 || sceKernelStartThread(thread, 0, nullptr) < 0) {
		running.store(false);
		sceAudioOutReleasePort(port);
		port = -1;
		return -1;
	}
	return 0;
}
extern "C" void ndspExit(void) {
	if (!running.exchange(false)) return;
	sceKernelWaitThreadEnd(thread, nullptr, nullptr);
	sceKernelDeleteThread(thread);
	sceAudioOutReleasePort(port);
	thread = port = -1;
}
extern "C" u32 ndspGetFrameCount(void) { return frameCount.load(std::memory_order_acquire); }
extern "C" void ndspSetMasterVol(float volume) { masterVolume = volume; }
extern "C" void ndspSetOutputMode(ndspOutputMode) {}
extern "C" void ndspSetClippingMode(ndspClippingMode mode) { softClip = mode == NDSP_CLIP_SOFT; }
extern "C" void ndspSetCallback(ndspCallback cb, void* data) {
	LightLock_Lock(&lock);
	callbackData = data;
	callback = cb;
	LightLock_Unlock(&lock);
}

extern "C" void ndspChnReset(int id) {
	LightLock_Lock(&lock);
	resetVoice(voices[id]);
	LightLock_Unlock(&lock);
}
extern "C" bool ndspChnIsPlaying(int id) {
	LightLock_Lock(&lock);
	const bool playing = voices[id].head != nullptr;
	LightLock_Unlock(&lock);
	return playing;
}
extern "C" u32 ndspChnGetSamplePos(int id) { return voices[id].pos; }
extern "C" void ndspChnSetPaused(int id, bool paused) { voices[id].paused = paused; }
extern "C" void ndspChnSetFormat(int id, u16 format) {
	LightLock_Lock(&lock);
	voices[id].format = format;
	LightLock_Unlock(&lock);
}
extern "C" void ndspChnSetInterp(int, ndspInterpType) {}
extern "C" void ndspChnSetRate(int id, float rate) { voices[id].rate = rate; }
extern "C" void ndspChnSetMix(int id, float mix[12]) {
	// Front left/right, with the surround pairs folded into the front.
	voices[id].mix[0] = mix[0] + mix[2];
	voices[id].mix[1] = mix[1] + mix[3];
}
extern "C" void ndspChnSetAdpcmCoefs(int id, u16 coefs[16]) {
	LightLock_Lock(&lock);
	for (int i = 0; i < 16; ++i) voices[id].coefs[i] = s16(coefs[i]);
	LightLock_Unlock(&lock);
}
extern "C" void ndspChnWaveBufClear(int id) {
	LightLock_Lock(&lock);
	Voice& v = voices[id];
	for (ndspWaveBuf* b = v.head; b; b = b->next) b->status = NDSP_WBUF_DONE;
	v.head = nullptr;
	v.primed = false;
	v.pos = 0;
	LightLock_Unlock(&lock);
}
extern "C" void ndspChnWaveBufAdd(int id, ndspWaveBuf* buf) {
	if (!buf || !buf->nsamples) return;
	LightLock_Lock(&lock);
	if (buf->status != NDSP_WBUF_QUEUED && buf->status != NDSP_WBUF_PLAYING) {
		buf->next = nullptr;
		buf->status = NDSP_WBUF_QUEUED;
		Voice& v = voices[id];
		if (!v.head) v.head = buf;
		else {
			ndspWaveBuf* b = v.head;
			while (b->next) b = b->next;
			b->next = buf;
		}
	}
	LightLock_Unlock(&lock);
}
extern "C" void ndspChnIirMonoSetEnable(int id, bool enable) {
	voices[id].iir = enable;
	if (!enable) voices[id].iirL = voices[id].iirR = 0.f;
}
// libctru's one-pole low-pass, y = (1 - e) x + e y', with e = exp(-2 pi f0 / Fs)
// at this mixer's rate.
extern "C" bool ndspChnIirMonoSetParamsLowPassFilter(int id, float f0) {
	const float e = std::exp(-2.f * float(M_PI) * f0 / float(OutputRate));
	voices[id].iirA = 1.f - e;
	voices[id].iirB = e;
	return true;
}
