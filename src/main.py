import sys
import time
import random

class PyChip8:
    def __init__(self, debug = False):
        self.reset()
        self.debug = debug

    def __showDebugInfo(self):
        if not self.debug: return
        print(f'\rPC: {self.pc}, T: {self.tdelay // 60}, V: {self.v}', end = '')

    def reset(self):
        self.memory = bytearray(4 * 1024)
        self.v = [0] * 16
        self.i = 0
        self.pc = 0xFFF
        self.tdelay = 0
        self.tsound = 0
        self.key = [0] * 16
        self.gfx = [64 * 32]
        self.stack = [0] * 16
        self.sp = 0


    def __decode_and_execute(self, opcode):
        # ❌ 0E00 clear_screen
        if opcode == 0x00E0: pass
        
        # 00EE subroutine return
        elif opcode == 0x00EE:
            self.pc = (self.memory[self.sp - 1] << 8) + self.memory[self.sp - 2]
            self.sp -= 2

        # ❌ 0NNN Calls machine code routine (RCA 1802 for COSMAC VIP) at address NNN. Not necessary for most ROMs. 
        elif opcode < 0x1000: pass
        
        # 1NNN jump to NNN
        elif opcode >= 0x1000 and opcode < 0x2000:
            nnn = opcode & 0x0FFF
            self.pc = nnn
        
        # 2NNN call subroutine at NNN
        elif opcode >= 0x2000 and opcode < 0x3000:
            self.memory[self.sp] = self.pc & 0x00FF
            self.sp += 1
            self.memory[self.sp] = (self.pc & 0xFF00) >> 8
            self.sp += 1
            nnn = opcode & 0x0FFF
            self.pc = nnn
        
        # 3XNN Skips the next instruction if VX equals NN. (Usually the next instruction is a jump to skip a code block) 
        elif opcode >= 0x3000 and opcode < 0x4000:
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.pc += 2 if self.v[x] == nn else 0
        
        # 4XNN Skips the next instruction if VX doesn't equal NN. (Usually the next instruction is a jump to skip a code block) 
        elif opcode >= 0x4000 and opcode < 0x5000:
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.pc += 2 if self.v[x] != nn else 0
        
        # 5XY0 Skips the next instruction if VX equals VY. (Usually the next instruction is a jump to skip a code block)
        elif opcode >= 0x5000 and opcode < 0x6000:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.pc += 2 if self.v[x] == self.v[y] else 0
        
        # 6XNN Sets VX to NN.
        elif opcode >= 0x6000 and opcode < 0x7000:
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.v[x] = nn
        
        # 7XNN Adds NN to VX. (Carry flag is not changed) 
        elif opcode >= 0x7000 and opcode < 0x8000:
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.v[x] = (self.v[x] + nn) % 0xFF
        
        # bit ops
        elif opcode >= 0x8000 and opcode < 0x9000:
            op = opcode & 0x000F
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            # 8XY0 Sets VX to the value of VY. 
            if op == 0:  self.v[x] = self.v[y]
            # 8XY1 Sets VX to VX or VY. (Bitwise OR operation) 
            elif op == 1: self.v[x] |= self.v[y]
            # 8XY2 Sets VX to VX and VY. (Bitwise AND operation) 
            elif op == 2: self.v[x] &= self.v[y]
            # 8XY3 Sets VX to VX xor VY. 
            elif op == 3: self.v[x] ^= self.v[y]
            # 8XY4 Adds VY to VX. VF is set to 1 when there's a carry, and to 0 when there isn't. 
            elif op == 4: 
                res = self.v[x] + self.v[y]
                self.v[x] = res % 0xFF
                self.v[0x0F] = 1 if res > 0x0F else 0
            # 8XY5 VY is subtracted from VX. VF is set to 0 when there's a borrow, and 1 when there isn't. 
            elif op == 5:
                res = self.v[x] - self.v[y]
                self.v[x] = res % 0xFF
                self.v[0x0F] = 1 if res < 0 else 0
            # 8XY6 Stores the least significant bit of VX in VF and then shifts VX to the right by 1.[b]
            elif op == 6:
                self.v[0x0F] = self.v[x] & 0x0001
                self.v[x] = self.v[x] >> 1
            # 8XY7 Sets VX to VY minus VX. VF is set to 0 when there's a borrow, and 1 when there isn't. 
            elif op == 7:
                res = self.v[y] - self.v[x]
                self.v[x] = res % 0xFF
                self.v[0x0F] = 0 if res < 0 else 1
            # 8XYE Stores the most significant bit of VX in VF and then shifts VX to the left by 1
            elif op == 0x0E:
                self.v[0x0F] = (self.v[x] & 0x8000) >> 15
                self.v[x] = self.v[x] << 1
            else:
                decode_err = True

        
        # 9XY0 Skips the next instruction if VX doesn't equal VY. (Usually the next instruction is a jump to skip a code block) 
        elif opcode >= 0x9000 and opcode < 0xA000:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.pc += 2 if self.v[x] != self.v[y] else 0
        
        # ANNN Sets I to the address NNN. 
        elif opcode >= 0xA000 and opcode < 0xB000:
            nnn = opcode & 0x0FFF
            self.i = nnn
        
        # BNNN Jumps to the address NNN plus V0. 
        elif opcode >= 0xB000 and opcode < 0xC000:
            nnn = opcode & 0x0FFF
            self.pc += self.v[0] + nnn
        
        # CXNN Sets VX to the result of a bitwise and operation on a random number (Typically: 0 to 255) and NN.
        elif opcode >= 0xC000 and opcode < 0xD000:
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.v[x] = random.randint(0, 256) & nn
        
        # ❌ DXYN Draws a sprite at coordinate (VX, VY) that has a width of 8 pixels and a height of N+1 pixels. Each row of 8 pixels is read as bit-coded starting from memory location I; I value doesn’t change after the execution of this instruction. As described above, VF is set to 1 if any screen pixels are flipped from set to unset when the sprite is drawn, and to 0 if that doesn’t happen 
        elif opcode >= 0xD000 and opcode < 0xE000: pass
        
        # keyop
        elif opcode >= 0xE000 and opcode < 0xF000:
            op = opcode & 0x00FF
            x = (opcode & 0x0F00) >> 8

            # ❌ Skips the next instruction if the key stored in VX is pressed. (Usually the next instruction is a jump to skip a code block) 
            if op == 0x9E: pass

            # ❌ EXA1 Skips the next instruction if the key stored in VX isn't pressed. (Usually the next instruction is a jump to skip a code block) 
            elif op == 0xA1: pass

            else:
                decode_err = True
        
        # mix
        elif opcode >= 0xF000:
            op = opcode & 0x00FF
            x = (opcode & 0x0F00) >> 8

            # FX07 Sets VX to the value of the delay timer. 
            if op == 0x07:
                self.v[x] = self.tdelay
            
            # ❌ FX0A A key press is awaited, and then stored in VX. (Blocking Operation. All instruction halted until next key event) 
            elif op == 0x0A: pass
            
            # FX15 Sets the delay timer to VX. 
            elif op == 0x15:
                self.tdelay = self.v[x]
            
            # FX18 Sets the sound timer to VX. 
            elif op == 0x18: 
                self.tsound = self.v[x]
            
            # FX1E Adds VX to I. VF is not affected. 
            elif op == 0x1E:
                self.i = (self.i + self.v[x]) % 0xFF
            
            # ❌ FX29 Sets I to the location of the sprite for the character in VX. Characters 0-F (in hexadecimal) are represented by a 4x5 font. 
            elif op == 0x29: pass
            
            # ❌ FX33 Stores the binary-coded decimal representation of VX, with the most significant of three digits at the address in I, the middle digit at I plus 1, and the least significant digit at I plus 2. (In other words, take the decimal representation of VX, place the hundreds digit in memory at location in I, the tens digit at location I+1, and the ones digit at location I+2.) 
            elif op == 0x33: pass
            
            # ❌ FX55 Stores V0 to VX (including VX) in memory starting at address I. The offset from I is increased by 1 for each value written, but I itself is left unmodified.[d]
            elif op == 0x55: pass
            
            # ❌ FX65 Fills V0 to VX (including VX) with values from memory starting at address I. The offset from I is increased by 1 for each value written, but I itself is left unmodified.[d]
            elif op == 0x07: pass
            
            else:
                decode_err = True
        else:
            decode_err = True

        
        if decode_err:
            print(f'ERROR DECODING INSTRUCTION: {hex(opcode)}')
        
    
    def __step(self):
        decode_err = False

        # fetch opcode
        opcode = self.memory[self.pc] << 8 | self.memory[self.pc + 1]
        self.pc += 2

        # decode opcode
        self.__decode_and_execute(opcode)
        
        # update timers
        if self.tdelay > 0: self.tdelay -= 1
        if self.tsound > 0:
            if self.tsound == 1:
                # beep
                pass
            self.tsound -= 1
    

    def run(self, rom_file):
        self.reset()

        # load rom_file contents

        while (True):
            self.__showDebugInfo()
            self.__step()
            
            # check draw flag
            # store keys

            # 60hz sync
            time.sleep(1 / 60)
        


def main(rom_file):
    
    emu = PyChip8(debug = True)
    emu.run(rom_file)


if __name__ == '__main__':
    _, rom_file = sys.argv
    main(rom_file)