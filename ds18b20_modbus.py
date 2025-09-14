#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import time
import datetime
import logging
from minimalmodbus import Instrument

class DS18B20:
    def __init__(self):
        # Настройка интерфейса 1-Wire
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        
        # Базовая директория для устройств 1-Wire
        self.base_dir = '/sys/bus/w1/devices/'
        
    def find_sensors(self):
        """Поиск всех подключенных датчиков DS18B20"""
        device_folders = glob.glob(self.base_dir + '28*')
        sensors = []
        
        for folder in device_folders:
            sensor_id = folder.split('/')[-1]
            sensors.append(sensor_id)
        
        return sensors
    
    def read_temp_raw(self, sensor_id):
        """Чтение сырых данных с датчика"""
        device_file = self.base_dir + sensor_id + '/w1_slave'
        
        try:
            with open(device_file, 'r') as f:
                lines = f.readlines()
            return lines
        except:
            return None
    
    def read_temp(self, sensor_id):
        """Чтение и преобразование температуры"""
        lines = self.read_temp_raw(sensor_id)
        
        if lines is None or len(lines) < 2:
            return None, None
        
        # Проверяем, что данные валидны (CRC = YES)
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self.read_temp_raw(sensor_id)
            if lines is None:
                return None, None
        
        # Ищем позицию температуры в данных
        equals_pos = lines[1].find('t=')
        if equals_pos == -1:
            return None, None
        
        # Извлекаем и преобразуем температуру
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        
        return temp_c
    
    def get_all_temperatures(self):
        """Получение температур со всех датчиков"""
        sensors = self.find_sensors()
        results = {}
        
        for sensor_id in sensors:
            temp_c = self.read_temp(sensor_id)
            if temp_c is not None:
                results[sensor_id] = temp_c
        
        return results

class ModbusRTUWriter:
    def __init__(self, port, baudrate, parity, stopbits, bytesize, timeout, slave_address):
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.timeout = timeout
        self.slave_address = slave_address
        self.instrument = None
        
        self.connect()
    
    def connect(self):
        """Подключение к Modbus устройству"""
        try:
            self.instrument = Instrument(
                self.port, 
                self.slave_address,
                close_port_after_each_call=True
            )
            
            # Настройка параметров связи
            self.instrument.serial.baudrate = self.baudrate
            self.instrument.serial.parity = self.parity
            self.instrument.serial.stopbits = self.stopbits
            self.instrument.serial.bytesize = self.bytesize
            self.instrument.serial.timeout = self.timeout
            
            logging.info(f"Modbus RTU подключен к {self.port}")
            
        except Exception as e:
            logging.error(f"Ошибка подключения к Modbus: {e}")
            self.instrument = None
    
    def write_temperature(self, register_address, temperature):
        """Запись температуры в регистр Modbus"""
        if self.instrument is None:
            self.connect()
            if self.instrument is None:
                return False
        
        try:
            # Преобразуем температуру в целое число (умножаем на 10 для сохранения одного знака после запятой)
            temp_value = int(temperature * 10)
            
            # Записываем значение в регистр
            self.instrument.write_register(register_address, temp_value, functioncode=6)
            
            logging.info(f"Записано в регистр {register_address}: {temperature:.1f}°C")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка записи в Modbus: {e}")
            self.instrument = None
            return False

def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('temperature_monitor.log'),
            logging.StreamHandler()
        ]
    )
    
    # Конфигурация Modbus RTU
    modbus_config = {
        "port": "/dev/ttyUSB0",
        "baudrate": 9600,
        "parity": 'E',
        "stopbits": 1,
        "bytesize": 8,
        "timeout": 2,
        "slave_address": 1
    }
    
    # Регистры для датчиков
    sensor_registers = {
        0: 4096,  # Первый датчик
        1: 4097   # Второй датчик
    }
    
    # Создаем экземпляры классов
    sensor_reader = DS18B20()
    modbus_writer = ModbusRTUWriter(**modbus_config)
    
    print("Поиск датчиков DS18B20...")
    
    # Ищем все датчики
    sensors = sensor_reader.find_sensors()
    
    if not sensors:
        print("Датчики не найдены! Проверьте подключение.")
        return
    
    print(f"Найдено датчиков: {len(sensors)}")
    
    for i, sensor_id in enumerate(sensors):
        print(f"Датчик {i}: {sensor_id} -> регистр {sensor_registers.get(i, 'N/A')}")
    
    print("\nНачинаем чтение и отправку данных (Ctrl+C для остановки):")
    print("-" * 60)
    
    try:
        while True:
            # Получаем температуры со всех датчиков
            temperatures = sensor_reader.get_all_temperatures()
            
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\nВремя: {current_time}")
            
            # Отправляем температуры по Modbus
            for i, (sensor_id, temp_c) in enumerate(temperatures.items()):
                if i < len(sensor_registers):
                    register = sensor_registers[i]
                    success = modbus_writer.write_temperature(register, temp_c)
                    
                    status = "✓" if success else "✗"
                    print(f"Датчик {i} ({sensor_id}): {temp_c:.2f}°C -> регистр {register} {status}")
                else:
                    print(f"Датчик {i} ({sensor_id}): {temp_c:.2f}°C (нет регистра)")
            
            time.sleep(5)  # Пауза между измерениями (5 секунд)
            
    except KeyboardInterrupt:
        print("\n\nРабота остановлена пользователем")
        logging.info("Программа остановлена пользователем")
    except Exception as e:
        print(f"\nПроизошла ошибка: {e}")
        logging.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    # Установите минимальную версию minimalmodbus: pip install minimalmodbus
    main()
