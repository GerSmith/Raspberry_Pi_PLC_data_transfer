#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import datetime
import logging
import requests
from minimalmodbus import Instrument

class WeatherFetcher:
    def __init__(self, city="Kurgan"):
        self.city = city
        self.base_url = "https://wttr.in"
    
    def get_current_temperature(self):
        """Получение текущей температуры из wttr.in"""
        try:
            # Получаем данные в JSON формате
            url = f"{self.base_url}/{self.city}?format=j1"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Парсим температуру
            data = response.json()
            temperature = float(data['current_condition'][0]['temp_C'])
            
            logging.info(f"Получена температура из wttr.in: {temperature}°C")
            return temperature
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка получения данных с wttr.in: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logging.error(f"Ошибка парсинга данных: {e}")
            return None

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
            logging.FileHandler('weather_modbus.log'),
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
    
    # Регистр для записи температуры погоды
    WEATHER_REGISTER = 4096  # Изменить на нужный регистр
    
    # Создаем экземпляры классов
    weather_fetcher = WeatherFetcher("Kurgan")
    modbus_writer = ModbusRTUWriter(**modbus_config)
    
    print("Сервис получения погоды и отправки по Modbus RTU")
    print("Город: Курган")
    print(f"Регистр для записи: {WEATHER_REGISTER}")
    print("\nНачинаем работу (Ctrl+C для остановки):")
    print("-" * 60)
    
    try:
        while True:
            # Получаем текущую температуру
            temperature = weather_fetcher.get_current_temperature()
            
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if temperature is not None:
                # Отправляем температуру по Modbus
                success = modbus_writer.write_temperature(WEATHER_REGISTER, temperature)
                
                status = "✓" if success else "✗"
                print(f"{current_time} - Температура: {temperature:.1f}°C -> регистр {WEATHER_REGISTER} {status}")
            else:
                print(f"{current_time} - Не удалось получить температуру")
            
            # Пауза между измерениями (5 минут = 300 секунд)
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\n\nРабота остановлена пользователем")
        logging.info("Программа остановлена пользователем")
    except Exception as e:
        print(f"\nПроизошла ошибка: {e}")
        logging.error(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    # Проверяем наличие необходимых библиотек
    try:
        import minimalmodbus
        import requests
    except ImportError as e:
        print(f"Ошибка: Не установлены необходимые библиотеки: {e}")
        print("Установите их командами:")
        print("pip install minimalmodbus")
        print("pip install requests")
        exit(1)
    
    main()
