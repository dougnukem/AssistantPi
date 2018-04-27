import os
import threading
import logging
import platform

from pocketsphinx import get_model_path
from pocketsphinx.pocketsphinx import Decoder

import alexapi.triggers as triggers
from .basetrigger import BaseTrigger

logger = logging.getLogger(__name__)


class PocketsphinxTrigger(BaseTrigger):


	type = triggers.TYPES.VOICE

	AUDIO_CHUNK_SIZE = 1024
	AUDIO_RATE = 16000

	_capture = None

	def __init__(self, config, trigger_callback, capture):
		super(PocketsphinxTrigger, self).__init__(config, trigger_callback, 'pocketsphinx')

		self._capture = capture

		self._enabled_lock = threading.Event()
		self._disabled_sync_lock = threading.Event()
		self._decoder = None

	def setup(self):
		# PocketSphinx configuration
		ps_config = Decoder.default_config()

		# Set recognition model to US
		ps_config.set_string('-hmm', os.path.join(get_model_path(), self._tconfig['language']))
		ps_config.set_string('-dict', os.path.join(get_model_path(), self._tconfig['dictionary']))

		# Specify recognition key phrase
		#ps_config.set_string('-keyphrase', self._tconfig['phrase'])
		#ps_config.set_float('-kws_threshold', float(self._tconfig['threshold']))

		### Multiple Hotwords
		#ps_config.set_string('-inmic', 'yes')
		ps_config.set_string('-kws', '/opt/AlexaPi/src/keyphrase.list')


		# Hide the VERY verbose logging information when not in debug
		if logging.getLogger('alexapi').getEffectiveLevel() != logging.DEBUG:

			null_path = '/dev/null'
			if platform.system() == 'Windows':
				null_path = 'nul'

			ps_config.set_string('-logfn', null_path)

		# Process audio chunk by chunk. On keyword detected perform action and restart search
		self._decoder = Decoder(ps_config)

	def run(self):
		thread = threading.Thread(target=self.thread, args=())
		thread.setDaemon(True)
		thread.start()

	def thread(self):
		while True:
			self._enabled_lock.wait()

			self._capture.handle_init(self.AUDIO_RATE, self.AUDIO_CHUNK_SIZE)

			self._decoder.start_utt()

			triggered = False
			#assistantTriggered = False
			voice_command = ""

			while not triggered:

				if not self._enabled_lock.isSet():
					break

				# Read from microphone
				data = self._capture.handle_read()

				# Detect if keyword/trigger word was said
				self._decoder.process_raw(data, False, False)

				triggered = self._decoder.hyp() is not None

			self._capture.handle_release()

			self._decoder.end_utt()

			self._disabled_sync_lock.set()

			if triggered:
				### Assistant Starts Here
				try:
					voice_command = self._decoder.hyp().hypstr
				except:
					voice_command = ""
				self._trigger_callback(self, voice_command)
				###

	def enable(self):
		self._enabled_lock.set()
		self._disabled_sync_lock.clear()

	def disable(self):
		self._enabled_lock.clear()
		self._disabled_sync_lock.wait()
