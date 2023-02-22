import discord
from discord.ext import commands as discord_commands
import gnuradio
import gnuradio.analog
import gnuradio.audio
import gnuradio.filter
import gnuradio.gr
import numpy
import osmosdr
import asyncio
import gnuradio.network
import struct
import socket

class CaptureBlock(gnuradio.gr.sync_block, discord.AudioSource):
    def __init__(self):
        gnuradio.gr.sync_block.__init__(
            self,
            name='Capture Block',
            in_sig=[numpy.float32],
            out_sig=[],
        )

        self.buffer = []
        self.buffer_len = 0
        self.playback_started = False
        self.min_buffer = int(48000 * 2 * 2 * 0.06)
        self.playback_length = int(48000 * 2 * 2 * 0.02)

        self.dtype = numpy.dtype('int16')
        self.dtype_i = numpy.iinfo(self.dtype)
        self.dtype_abs_max = 2 ** (self.dtype_i.bits - 1)

    def work(self, input_items, output_items):
        buf = self._convert(input_items[0])
        self.buffer_len += len(buf)
        self.buffer.append(buf)

        self.playback_started = self.buffer_len > self.min_buffer
        return len(input_items[0])

    def _convert(self, f):
        f = numpy.asarray(f)
        f = f * self.dtype_abs_max
        f = f.clip(self.dtype_i.min, self.dtype_i.max)
        f = f.astype(self.dtype)
        f = f.repeat(2)
        f = f.tobytes()
        return f

    def read(self):
        if not self.playback_started:
            return bytes(self.playback_length)
        if self.buffer_len < self.playback_length:
            #print("Warning: low buffer")
            return bytes(self.playback_length)

        buf = bytearray(self.playback_length)
        #print("self.playback_length:", self.playback_length, "self.buffer_len:", self.buffer_len)
        i = 0
        while i < self.playback_length:
            next_buf = self.buffer.pop(0)
            next_buf_len = len(next_buf)
            self.buffer_len -= next_buf_len
            if i + next_buf_len > self.playback_length:
                putback_len = next_buf_len - (self.playback_length - i)
                putback = next_buf[-putback_len:]
                self.buffer.insert(0, putback)
                self.buffer_len += putback_len
                next_buf = next_buf[:-putback_len]
                next_buf_len = len(next_buf)

            buf[i:i + next_buf_len] = next_buf
            i += next_buf_len

        return buf


class RadioBlock(gnuradio.gr.top_block):
    def __init__(self):
        gnuradio.gr.top_block.__init__(self, "Discord Radio")

        self.source = gnuradio.network.udp_source(gnuradio.gr.sizeof_float, 1, 1234, 0, 1472, False, False, False) # type, vect len?, port, header, packet size, notify missed frames, source 0 if no data, ipv6 support
        self.capture_block = CaptureBlock()

        self.connect((self.source, 0), (self.capture_block, 0))


intents = discord.Intents.default()
intents.message_content = True
bot = discord_commands.Bot(command_prefix=discord_commands.when_mentioned_or('!'),
                           description='Radio bot',
                           intents=intents)


@bot.event
async def on_ready():
    print('Logged on')


class BotCommands(discord_commands.Cog):
    def __init__(self, bot, radio):
        self.bot = bot
        self.radio = radio

    @discord_commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    """
    @discord_commands.command()
    async def fm(self, ctx, *, freq):
        freq_mhz = float(freq)
        freq = float(freq_mhz) * 1000000
        #self.radio.source.set_center_freq(freq)

        if not ctx.voice_client.is_playing():
            source = discord.PCMVolumeTransformer(self.radio.capture_block)
            ctx.voice_client.play(source)
            self.radio.start()

        await ctx.send(f'Tuning {freq_mhz}MHz FM')
    """

    @discord_commands.command()
    async def msg(self, ctx, *, inp):
        fields = bytes(inp, 'utf-8').split(b' ')
        name_str = fields[0]
        value_str = fields[1] if len(fields) > 1 else b''
        print("name_str:", name_str, "value_str:", value_str)

        floating = True
        try:
            float(value_str)
        except ValueError:
            print("note: not a double?")
            floating = False

        if floating:
            value = struct.pack('>d', float(value_str))
            value_data = b''.join((b'\x04', value))
        else:
            value_len = struct.pack('>H', len(value_str))
            value_data = b''.join((b'\x02', value_len, value_str))

        name_len = struct.pack('>H', len(name_str))
        full_data = b''.join((b'\x07\x02', name_len, name_str, value_data))

        print("full_data:", full_data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(full_data, ('127.0.0.1', 1325))

    @discord_commands.command()
    async def preset(self, ctx, *, preset):
        await self.msg(ctx, inp=''.join(('preset ', preset)))

    @discord_commands.command()
    async def start(self, ctx):
        if not ctx.voice_client.is_playing():
            source = discord.PCMVolumeTransformer(self.radio.capture_block)
            ctx.voice_client.play(source)
            self.radio.start()

        await ctx.send(f'Started playing')

    @discord_commands.command()
    async def stop(self, ctx):
        self.radio.stop()
        await ctx.voice_client.disconnect() 

    @start.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send('You must be in a voice channel to use that')
                raise discord_commands.CommandError('User not connected to voice channel')

async def main():
    import sys
    token = sys.argv[1]
    top_block = RadioBlock()
    discord.utils.setup_logging()
    async with bot:
        await bot.add_cog(BotCommands(bot, top_block))
        await bot.start(token)

if __name__ == '__main__':
    asyncio.run(main())
