import sys
from os import path
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import unittest
from unittest import IsolatedAsyncioTestCase

from cogs.public import Public
# try:
from mocking import *
# except:
#     from .mocking import *


class PublicTest(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(self):
        self.logger = MockLogger()
        self.cog = Public(MockBot(self.logger))
        self.cog.logger = self.logger

        self.general_channel = MockChannel("general")
        channels = [self.general_channel]

        self.unreserved = MockColour(0)
        self.mockRoles = {
            "everyone"  : MockRole("everyone", self.unreserved),
            "Training"  : MockRole("Training", self.unreserved),
            "Pickup"    : MockRole("Pickup", self.unreserved),
            "Recruit"   : MockRole("Recruit", MockColour(1)),
            "Admin"     : MockRole("Admin", MockColour(2))
        }

        roles = [
            self.mockRoles["everyone"], self.mockRoles["Training"], self.mockRoles["Pickup"], 
            self.mockRoles["Recruit"], self.mockRoles["Admin"]
        ]
        
        self.guild = MockGuild("ARCOMM", channels, roles)
        self.user = MockUser(self.guild, "Sven_Axeman", [self.mockRoles["everyone"], self.mockRoles["Admin"], self.mockRoles["Pickup"]])

    async def test_members(self):
        message = await self.user.mock_send(self.general_channel, ".members pickup")
        ctx = MockContext(message)

        members = await self.cog.members(self.cog, ctx, "nonexistingrole")
        self.assertEqual(members, None)

        members = await self.cog.members(self.cog, ctx, "adm")
        self.assertEqual(members, [self.user])

        user2 = MockUser(self.guild, "Little_scot", [self.mockRoles["everyone"], self.mockRoles["Admin"]])
        members = await self.cog.members(self.cog, ctx, "admin")
        self.assertEqual(members, [user2, self.user])

    async def test_myroles(self):
        message = await self.user.mock_send(self.general_channel, ".myroles")
        ctx = MockContext(message)

        roles = await self.cog.myroles(self.cog, ctx)
        self.assertEqual(roles, [self.mockRoles["Admin"], self.mockRoles["Pickup"]])

    # TODO: async def test_opstart(self):

    # TODO: async def test_optime(self):

    # TODO: async def test_ping(self):

    # TODO: async def test_repo(self):

if __name__ == '__main__':
    unittest.main()
