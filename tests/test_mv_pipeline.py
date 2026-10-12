import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from music_router import MusicProviderRouter
from video_engine import VideoEngine, MAX_DURATION


class PipelineRegressionTests(unittest.TestCase):
    def test_song_never_calls_bgm_when_song_providers_are_missing(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            bgm = Mock()
            router = MusicProviderRouter(bgm, directory)
            with self.assertRaisesRegex(RuntimeError, '完整歌曲需要'):
                asyncio.run(router.generate(lyrics='舞啊舞，舞魅來！'))
            bgm.generate_local_bgm.assert_not_called()

    def test_instrumental_still_uses_bgm(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            bgm = Mock()
            bgm.get_style_info.return_value = {'tags': 'war drums'}
            bgm.generate_local_bgm.return_value = {'engine': 'fallback', 'path': 'test.wav'}
            result = asyncio.run(MusicProviderRouter(bgm, directory).generate(lyrics=''))
            self.assertFalse(result['full_song'])
            bgm.generate_local_bgm.assert_called_once()

    def test_67_seconds_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / 'audio.wav'
            audio.touch()
            engine = VideoEngine(directory)
            with patch.object(engine, '_render_segment'), patch.object(engine, '_concat_segments'), patch.object(engine, '_mux_final') as mux:
                mux.side_effect = lambda video, audio, final, duration, srt, burn: (final.touch() or False)
                result = engine.render_mv(['one.png', 'two.png'], str(audio), duration=67)
            self.assertEqual(result['duration'], 67)
            self.assertEqual((result['width'], result['height'], result['fps']), (720, 1280, '24'))
            self.assertEqual(mux.call_args.args[3], 67)

    def test_over_limit_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / 'audio.wav'
            audio.touch()
            with self.assertRaisesRegex(RuntimeError, '不會自動截短'):
                VideoEngine(directory).render_mv(['one.png'], str(audio), duration=MAX_DURATION + 1)


if __name__ == '__main__':
    unittest.main()
