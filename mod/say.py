"""This module is an example module that is a base skeleton for many other
modules. It has a single command that simply says its arguments"""
from utils import Cog
from discord.ext import commands


__author__ = "Dark Kirb"
__license__ = "Public domain"
__website__ = None
__version__ = "1.0"


class Say(Cog):
    @commands.command()
    async def say(self, ctx, *, msg: str):
        """Output the arguments as a message"""
        await ctx.send(msg)

    def __global_check_once(self, ctx):
        return self.check_once(ctx)


def setup(bot):
    global cog
    cog = Say(bot)
