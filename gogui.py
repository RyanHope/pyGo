#!/usr/bin/env python

from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall

from collections import deque

import argparse
import os

import pygame

pygame.display.init()
pygame.font.init()

class Game(object):

    colors = ['black','white']
    rgbs = [(0,0,0),(255,255,255)]

    def __init__(self, gtp, boardsize=19, komi=5.5, caption=''):
        self.gtp = gtp
        self.boardsize = boardsize
        self.edgedist = None
        if self.boardsize < 26 and self.boardsize > 12:
            self.edgedist = 4
        elif self.boardsize < 13 and self.boardsize > 6:
            self.edgedist = 3
        self.komi = komi
        self.player = 0
        self.plays = []

        self.window = ( 550, 600 )
        self.setConstants()

        pygame.display.set_caption(caption)
        self.screen = pygame.display.set_mode( self.window, 0 )
        self.worldsurf = self.screen.copy()
	self.worldsurf_rect = self.worldsurf.get_rect()
	self.gamesurf = pygame.Surface(self.game)
	self.gamesurf_rect = self.gamesurf.get_rect()
	self.gamesurf_rect.midbottom = self.worldsurf_rect.midbottom

        self.gtp._cmd('boardsize %d' % self.boardsize)
        self.gtp._cmd('komi %f' % self.komi)

        self.lc = LoopingCall(self.update)
        self.lc.start(1./30)

    def setConstants(self):
        m = min(self.window) * 1.
        self.game = (m, m)
        self.cell = m / (self.boardsize + 1)
        self.fontsize = int(self.cell/2)
        self.labelfont = pygame.font.Font(None, self.fontsize)

    def draw_text( self, text, font, color, loc, surf, justify = "center" ):
        t = font.render( text, True, color )
        tr = t.get_rect()
        setattr( tr, justify, loc )
        surf.blit( t, tr )
        return tr

    def draw(self):
        self.worldsurf.fill( (196,196,255) )
        self.gamesurf.fill( (196,196,255) )
        l = int( (self.boardsize - 1) * self.cell )
        x = self.cell
        y = self.cell
        for i in range(0,self.boardsize):
            pygame.draw.line(self.gamesurf, (128,128,128), (x,y+(i*self.cell)), (x+l,y+(i*self.cell)))
            pygame.draw.line(self.gamesurf, (128,128,128), (x+(i*self.cell),y), (x+(i*self.cell),y+l))
            self.draw_text(str(self.boardsize-i), self.labelfont, (128,128,128), (x-(self.cell*.75), y+(i*self.cell)), self.gamesurf)
            self.draw_text(str(self.boardsize-i), self.labelfont, (128,128,128), (x+l+(self.cell*.75), y+(i*self.cell)), self.gamesurf)
            self.draw_text(chr(i+65), self.labelfont, (128,128,128), (x+(i*self.cell),y*.25), self.gamesurf)
            self.draw_text(chr(i+65), self.labelfont, (128,128,128), (x+(i*self.cell),1.75*y+l), self.gamesurf)

        if self.edgedist:
            handicaps = [
                (self.edgedist-1,self.edgedist-1),
                (self.boardsize-self.edgedist,self.boardsize-self.edgedist),
                (self.edgedist-1,self.boardsize-self.edgedist),
                (self.boardsize-self.edgedist,self.edgedist-1)
                ]
            if self.boardsize % 2:
                handicaps.append((self.boardsize/2,self.boardsize/2))
                handicaps.append((self.boardsize/2,self.edgedist-1)),
                handicaps.append((self.boardsize/2,self.boardsize-self.edgedist)),
                handicaps.append((self.edgedist-1,self.boardsize/2)),
                handicaps.append((self.boardsize-self.edgedist,self.boardsize/2))
            for h in handicaps:
                pygame.draw.circle(self.gamesurf, (128,128,128), (int(x+h[0]*self.cell),int(y+h[1]*self.cell)), int(self.cell*.15))
            
        if self.plays:
            for p,r,c in self.plays:
                r = self.boardsize - r
                pygame.draw.circle(self.gamesurf, self.rgbs[p], (int(x+c*self.cell),int(y+r*self.cell)), int(self.cell*.45))
            p,r,c = self.plays[-1]
            r = self.boardsize - r
            pygame.draw.circle(self.gamesurf, self.rgbs[int(not p)], (int(x+c*self.cell),int(y+r*self.cell)), int(self.cell*.3), 1)

        self.worldsurf.blit( self.gamesurf, self.gamesurf_rect )
        self.screen.blit( self.worldsurf, self.worldsurf_rect )
	pygame.display.flip()

    def play(self, data, player):
        c = ord(data[1][0])-65
        r = int(data[1][1:])
        self.plays.append((player, r, c))

    def processEvents(self):
        for event in pygame.event.get():
	    if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.gtp._cmd("genmove %s" % self.colors[self.player], self.play, self.player)
                    self.player = int(not self.player)

    def update(self):
        self.draw()
        self.processEvents()

class GTP(protocol.ProcessProtocol):

    delimiter = '\n\r'
    __out_buffer = ''
    __err_buffer = ''
    MAX_LENGTH = 16384

    def __init__(self):
        self.cmdID = 0
        self.game = None
        self.callbacks = deque()

    def _cmd(self, message, callback=None, *args, **kwargs):
        self.cmdID += 1
        self.callbacks.appendleft((callback, args, kwargs))
        self.transport.write('%d %s\n' % (self.cmdID, message))

    def _got_version(self, data, name):
        self.game = Game(self, caption='%s (%s)' % (name, data[1]))

    def _got_name(self, data):
        self._cmd('version', self._got_version, ' '.join(data[1:]))
                             
    def connectionMade(self):
        self._cmd('name', self._got_name)

    def outReceived(self, data):
        self.__out_buffer = self.__out_buffer+data
        while True:
            try:
                line, self.__out_buffer = self.__out_buffer.split(self.delimiter, 1)
            except ValueError:
                if len(self.__out_buffer) > self.MAX_LENGTH:
                    line, self.__out_buffer = self.__out_buffer, ''
                    return self.lineLengthExceeded(line)
                break
            else:
                linelength = len(line)
                if linelength > self.MAX_LENGTH:
                    exceeded = line + self.__out_buffer
                    self.__out_buffer = ''
                    return self.lineLengthExceeded(exceeded)
                self.lineReceived(line)

    def lineReceived(self, line):
        cb,a,kw = self.callbacks.pop()
        if cb:
            cb(line.split(), *a, **kw)
    
if __name__ == '__main__':

    gnugopath = None
    if os.environ.has_key('GNUGO'):
        gnugopath = os.environ['GNUGO']

    parser = argparse.ArgumentParser( formatter_class = argparse.ArgumentDefaultsHelpFormatter )
    parser.add_argument( '--gnugo', action = "store", dest = "gnugo", help = 'Path containing gnugo binary', default=gnugopath )
    parser.add_argument( '--cpucolor', action = "store", choices = ['white','black'], dest = "cpucolor", help = 'Color of CPU opponent', default='white' )
    parser.add_argument( '--boardsize', action = "store", dest = "boardsize", help = 'Board size', default=19 )

    args = parser.parse_args()
    gnugo = os.path.join(gnugopath, 'gnugo.exe')
    
    cpu = reactor.spawnProcess(GTP(), gnugo, [gnugo, '--mode=gtp'], env=None)
    reactor.run()
