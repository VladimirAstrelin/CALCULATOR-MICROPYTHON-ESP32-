# Импортируем необходимые модули
from machine import Pin, SoftI2C, Timer  # Для работы с пинами, I2C и таймерами
import ssd1306  # Для работы с OLED дисплеем
import time  # Для работы со временем
import math  # Для математических функций
import re  # Для регулярных выражений
from calc_parser import evaluate_expression  # Наш парсер математических выражений

# ВЕРСИЯ 7.1 - ИСПРАВЛЕННО ОТОБРАЖЕНИЕ КОНСТАНТ

# ===== НАСТРОЙКА ДИСПЛЕЯ =====
# Создаем I2C интерфейс на пинах 47 (SCL) и 21 (SDA)
i2c = SoftI2C(scl=Pin(47), sda=Pin(21))
W = 128  # Ширина дисплея в пикселях
H = 64   # Высота дисплея в пикселях
oled = ssd1306.SSD1306_I2C(W, H, i2c)  # Создаем объект дисплея

# ===== НАСТРОЙКА GPIO =====
# Создаем список пинов для строк матричной клавиатуры (выходы)
rows = [
    Pin(15, Pin.OUT),  # Строка 0
    Pin(16, Pin.OUT),  # Строка 1  
    Pin(17, Pin.OUT),  # Строка 2
    Pin(18, Pin.OUT)   # Строка 3
]

# Создаем список пинов для столбцов матричной клавиатуры (входы с подтяжкой к питанию)
cols = [
    Pin(35, Pin.IN, Pin.PULL_UP),  # Столбец 0
    Pin(36, Pin.IN, Pin.PULL_UP),  # Столбец 1
    Pin(37, Pin.IN, Pin.PULL_UP),  # Столбец 2
    Pin(39, Pin.IN, Pin.PULL_UP),  # Столбец 3
    Pin(40, Pin.IN, Pin.PULL_UP),  # Столбец 4
    Pin(41, Pin.IN, Pin.PULL_UP)   # Столбец 5
]

# Создаем словарь для навигационных кнопок
nav_buttons = {
    'up':    Pin(42, Pin.IN, Pin.PULL_UP),    # Кнопка ВВЕРХ
    'down':  Pin(43, Pin.IN, Pin.PULL_UP),    # Кнопка ВНИЗ
    'left':  Pin(44, Pin.IN, Pin.PULL_UP),    # Кнопка ВЛЕВО
    'right': Pin(45, Pin.IN, Pin.PULL_UP),    # Кнопка ВПРАВО
    'enter': Pin(46, Pin.IN, Pin.PULL_UP)     # Кнопка ВВОД
}

# Инициализация строк - устанавливаем все в высокий уровень (1)
for r in rows:
    r.value(1)

# ===== РАСКЛАДКА КЛАВИАТУРЫ =====
# Обычная раскладка (базовый режим)
keymap_normal = [
    ['7', '8', '9', '/', 'C', 'BS'],     # Ряд 1: цифры 7-9, деление, очистка, backspace
    ['4', '5', '6', '*', '(', ')'],      # Ряд 2: цифры 4-6, умножение, скобки
    ['1', '2', '3', '-', '=', 'SHIFT'],  # Ряд 3: цифры 1-3, минус, равно, переключение режима
    ['0', '.', '%', '+', '^', 'MENU']    # Ряд 4: ноль, точка, процент, плюс, степень, меню
]

# Альтернативная раскладка (научный режим)
# ЗАМЕНИЛИ 'sqr' на 'sqrt' для ясности и убрали неиспользуемые '[' и ']'
keymap_shift = [
    ['sin', 'cos', 'tan', 'log', 'ln', 'BS'],     # Ряд 1: тригонометрия, логарифмы, backspace
    ['pi', 'e', 'sqrt', '!', '(', ')'],           # Ряд 2: константы, корень, факториал, скобки
    ['1/x', 'x²', 'x³', '±', '=', 'SHIFT'],       # Ряд 3: обратное, квадрат, куб, смена знака, равно, переключение
    ['0', '.', '%', '+', '^', 'MENU']             # Ряд 4: ноль, точка, процент, плюс, степень, меню
]

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
stable_matrix_keys = []  # Стабильное состояние клавиш матрицы (после устранения дребезга)
last_matrix_keys = []    # Предыдущее состояние клавиш матрицы
stable_nav_keys = []     # Стабильное состояние навигационных кнопок
last_nav_keys = []       # Предыдущее состояние навигационных кнопок
pressed_keys_history = set()  # История нажатых клавиш (для обнаружения новых нажатий)
pressed_nav_history = set()   # История нажатых навигационных кнопок

scan_flag = bytearray(1)  # Флаг для синхронизации сканирования клавиатуры
display_tick = 0          # Счетчик для обновления дисплея

# Переменные калькулятора
expression = ""      # Полное математическое выражение (например: "789+1")
current_input = "0"  # Текущее вводимое число
result = ""          # Результат вычислений
shift_mode = False   # Режим научного калькулятора (True - научный, False - базовый)
menu_mode = False    # Режим меню (True - открыто меню, False - калькулятор)
menu_position = 0    # Текущая позиция в меню
last_nav_action = 0  # Время последнего нажатия навигационной кнопки
reset_on_next_input = False  # Флаг сброса при следующем вводе

# Режим "О программе"
about_mode = False   # Режим просмотра информации о программе
about_page = 0       # Текущая страница в режиме "О программе"
about_pages = [      # Страницы с информацией
    # Убрали строку "Firmware: 7.1" как просили
    ["CALCULATOR v7.1", "Author: VLAD", "ESP32-S3", ""],  # Страница 1: основная информация
    ["FIXED CONSTANTS:", "pi and e display", "shorter values", "fits screen"],  # Страница 2: о константах
    ["HOW TO USE:", "Use 2*(-3)", "for negative", "multiplication"],  # Страница 3: инструкция
    ["NAVIGATION:", "UP/DOWN=Scroll", "ENTER=Select", "MENU=Exit"]   # Страница 4: управление
]

# Математические константы (укороченные для лучшего отображения на экране)
PI = 3.14159265358979   # Число π с 14 знаками после запятой
E = 2.718281828459045   # Число e с 15 знаками после запятой

DEBUG = False  # Режим отладки (вывод дополнительной информации)

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С ДИСПЛЕЕМ =====
def center_text(text, y):
    """Выравнивает текст по центру экрана на заданной высоте y"""
    x = (W - len(text) * 8) // 2  # Вычисляем позицию x для центрирования (8 пикселей на символ)
    if x < 0:  # Если текст слишком длинный, начинаем с левого края
        x = 0
    oled.text(text, x, y)  # Выводим текст на дисплей

def draw_inverted_box(text, x, y):
    """Рисует текст в инвертированном прямоугольнике (белый фон, черный текст)"""
    width = len(text) * 8 + 4  # Ширина прямоугольника (8 пикселей на символ + отступы)
    height = 10  # Высота прямоугольника
    # Рисуем белый прямоугольник (заливаем область)
    oled.fill_rect(x, y, width, height, 1)
    # Рисуем черный текст поверх белого прямоугольника
    oled.text(text, x + 2, y + 1, 0)

def draw_large_inverted_result(text, y):
    """Рисует крупный инвертированный результат по центру экрана"""
    text_width = len(text) * 8  # Ширина текста в пикселях
    box_width = text_width + 8  # Ширина прямоугольника с отступами
    box_height = 14  # Высота прямоугольника
    x_pos = (W - box_width) // 2  # Позиция x для центрирования
    
    # Рисуем белый прямоугольник
    oled.fill_rect(x_pos, y, box_width, box_height, 1)
    # Рисуем черный текст поверх с отступами
    oled.text(text, x_pos + 4, y + 3, 0)

def update_display():
    """Обновляет содержимое дисплея в зависимости от текущего режима"""
    oled.fill(0)  # Очищаем дисплей (заполняем черным)
    
    if about_mode:
        # Режим "О программе"
        page = about_pages[about_page]  # Получаем текущую страницу
        for i, line in enumerate(page):
            if i < 4:  # Выводим до 4 строк на странице
                center_text(line, 5 + i * 12)  # Центрируем каждую строку
        # Отображаем номер страницы и подсказку по управлению
        oled.text(f"Page {about_page + 1}/{len(about_pages)}", 0, 55)
        oled.text("UP/DOWN=MENU", 70, 55)
        
    elif menu_mode:
        # Режим меню
        center_text("MAIN MENU", 0)  # Заголовок меню по центру
        menu_items = ["Basic Calc", "Scientific", "Settings", "About"]  # Пункты меню
        
        # Отображаем все пункты меню
        for i, item in enumerate(menu_items):
            if i == menu_position:
                # Текущий выбранный пункт выделяем стрелкой
                oled.text(f"> {item}", 10, 15 + i * 10)
            else:
                # Остальные пункты без выделения
                oled.text(f"  {item}", 10, 15 + i * 10)
        oled.text("ENTER=Select", 0, 55)  # Подсказка внизу экрана
        
    else:
        # ОСНОВНОЙ РЕЖИМ КАЛЬКУЛЯТОРА (в стиле Windows Calculator)
        
        # 1. Верхняя строка - полное выражение с текущим вводом
        display_expr = expression  # Начинаем с основного выражения
        
        # Добавляем текущий ввод к выражению, если он не нулевой
        if current_input != "0" and current_input != "Error":
            display_expr += current_input
        
        # Добавляем знак "=" если есть результат вычислений
        if result:
            display_expr += "="
        
        # Обрезаем выражение если оно слишком длинное
        if display_expr:
            if len(display_expr) > 20:
                display_expr = "..." + display_expr[-17:]  # Показываем последние 17 символов
            oled.text(display_expr, 0, 2)  # Выводим выражение в верхней части
        
        # 2. Основное поле - инвертированный результат или обычный текущий ввод
        display_text = result if result else current_input  # Что показывать: результат или ввод
        
        if display_text:
            # Обрезаем текст если он слишком длинный
            if len(display_text) > 16:
                display_text = display_text[-16:]  # Показываем последние 16 символов
            
            # ИНВЕРТИРОВАННЫЙ РЕЗУЛЬТАТ ДЛЯ ВСЕХ РЕЖИМОВ
            if result or (not expression and current_input != "0" and current_input != "Error"):
                # Показываем результат вычислений ИЛИ прямое вычисление научной функции
                draw_large_inverted_result(display_text, 22)  # Крупный инвертированный текст
            else:
                # Текущий ввод в выражении - обычный текст по центру
                text_width = len(display_text) * 8
                x_pos = (W - text_width) // 2
                oled.text(display_text, x_pos, 25)  # Обычный текст
        
        # 3. Инвертированный индикатор режима в правом нижнем углу
        mode_text = "S" if shift_mode else "B"  # S - научный, B - базовый
        draw_inverted_box(mode_text, W - 12, H - 10)  # Маленький инвертированный квадрат
    
    try:
        oled.show()  # Обновляем дисплей (выводим буфер на экран)
    except OSError:
        pass  # Игнорируем ошибки вывода (например, если дисплей отключен)

# ===== СКАНИРОВАНИЕ КЛАВИАТУРЫ =====
def fast_scan_matrix():
    """Быстро сканирует матричную клавиатуру и возвращает нажатые клавиши"""
    pressed_keys = []  # Список нажатых клавиш
    
    # Проходим по всем строкам матрицы
    for row_num, row_pin in enumerate(rows):
        row_pin.value(0)  # Активируем текущую строку (устанавливаем в 0)
        time.sleep_us(80)  # Короткая задержка для стабилизации
        
        # Проверяем все столбцы в активированной строке
        for col_num, col_pin in enumerate(cols):
            if col_pin.value() == 0:  # Если клавиша нажата (сигнал 0)
                time.sleep_us(50)  # Задержка для устранения дребезга
                if col_pin.value() == 0:  # Подтверждаем нажатие
                    # Определяем символ клавиши в зависимости от режима
                    if shift_mode:
                        key_char = keymap_shift[row_num][col_num]  # Научный режим
                    else:
                        key_char = keymap_normal[row_num][col_num]  # Базовый режим
                    pressed_keys.append((row_num, col_num, key_char))  # Добавляем в список
        
        row_pin.value(1)  # Деактивируем строку
        time.sleep_us(40)  # Короткая задержка
    
    return pressed_keys  # Возвращаем список нажатых клавиш

def fast_scan_nav():
    """Сканирует навигационные кнопки и возвращает нажатые"""
    pressed_nav = []  # Список нажатых навигационных кнопок
    for name, button in nav_buttons.items():  # Проходим по всем кнопкам
        try:
            if button.value() == 0:  # Если кнопка нажата
                time.sleep_us(50)  # Задержка для устранения дребезга
                if button.value() == 0:  # Подтверждаем нажатие
                    pressed_nav.append(name)  # Добавляем имя кнопки в список
        except:
            pass  # Игнорируем ошибки чтения (для надежности работы)
    return pressed_nav  # Возвращаем список нажатых кнопок

def debounce_keys(current_matrix, current_nav):
    """Устраняет дребезг контактов, сравнивая текущее и предыдущее состояние"""
    global last_matrix_keys, last_nav_keys, stable_matrix_keys, stable_nav_keys
    
    # Преобразуем текущие и предыдущие состояния в множества для сравнения
    current_set = set((r, c, k) for r, c, k in current_matrix)
    last_set = set((r, c, k) for r, c, k in last_matrix_keys)
    
    # Если текущее состояние совпадает с предыдущим - клавиши стабильны
    if current_set == last_set:
        stable_matrix_keys = current_matrix
    else:
        stable_matrix_keys = []  # Иначе - состояние нестабильно
    
    # Аналогично для навигационных кнопок
    if set(current_nav) == set(last_nav_keys):
        stable_nav_keys = current_nav
    else:
        stable_nav_keys = []
    
    # Сохраняем текущее состояние как предыдущее для следующего вызова
    last_matrix_keys = current_matrix
    last_nav_keys = current_nav

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def round_result(value):
    """Округляет числовое значение для устранения погрешностей вычислений"""
    # Сначала проверяем, не является ли значение ошибкой
    if isinstance(value, str) and value == "Error":
        return "Error"
    
    try:
        # Преобразуем значение в число, если оно строковое
        if isinstance(value, str):
            num_value = float(value)
        else:
            num_value = value
            
        # Округляем до 12 знаков после запятой для точности
        rounded = round(num_value, 12)
        
        # Если число очень близко к целому - делаем его целым
        if abs(rounded - round(rounded)) < 1e-10:
            rounded = round(rounded)
        
        # Если число целое - убираем .0
        if rounded == int(rounded):
            return str(int(rounded))
        else:
            # Форматируем с минимальным количеством знаков
            result_str = f"{rounded:.10g}"
            # Убираем лишние нули в конце дробной части
            if '.' in result_str:
                result_str = result_str.rstrip('0').rstrip('.')
            return result_str
            
    except:
        return str(value)  # В случае ошибки возвращаем строковое представление

# ===== УЛУЧШЕННАЯ ЛОГИКА КАЛЬКУЛЯТОРА =====
def handle_digit_input(digit):
    """Обрабатывает ввод цифр"""
    global current_input, reset_on_next_input, result
    
    # Если текущий ввод "0" или "Error", или нужен сброс - заменяем текущий ввод
    if current_input == "0" or current_input == "Error" or reset_on_next_input:
        current_input = digit
        reset_on_next_input = False
        result = ""  # Сбрасываем результат при новом вводе
    else:
        # Добавляем цифру к текущему вводу (если не превышен лимит)
        if len(current_input) < 20:
            current_input += digit
        result = ""  # Сбрасываем результат при продолжении ввода

def handle_decimal_point():
    """Обрабатывает ввод десятичной точки"""
    global current_input, reset_on_next_input, result
    
    # Если текущий ввод "0" или нужен сброс - начинаем с "0."
    if current_input == "0" or current_input == "Error" or reset_on_next_input:
        current_input = "0."
        reset_on_next_input = False
        result = ""
    # Если точки еще нет в числе - добавляем ее
    elif '.' not in current_input:
        current_input += '.'
        result = ""

def handle_backspace():
    """Обрабатывает удаление последнего символа (Backspace)"""
    global current_input, expression, reset_on_next_input, result
    
    if current_input == "Error":
        # Если была ошибка - полностью сбрасываем калькулятор
        current_input = "0"
        expression = ""
        result = ""
        reset_on_next_input = False
    elif len(current_input) > 1:
        # Удаляем последний символ
        current_input = current_input[:-1]
    else:
        # Если остался один символ - сбрасываем на "0"
        current_input = "0"
    reset_on_next_input = False
    result = ""  # Сбрасываем результат при редактировании

def handle_clear():
    """Обрабатывает полную очистку калькулятора (C)"""
    global current_input, expression, reset_on_next_input, result
    current_input = "0"
    expression = ""
    result = ""
    reset_on_next_input = False

def handle_operation(op):
    """Обрабатывает ввод математических операций (+, -, *, /)"""
    global current_input, expression, reset_on_next_input, result
    
    if current_input != "Error":  # Если нет ошибки
        reset_on_next_input = False
        result = ""  # Сбрасываем результат при новом вводе
        
        # Специальная обработка для унарного минуса (отрицательные числа)
        if op == '-' and current_input == "0":
            current_input = "-"  # Начинаем ввод отрицательного числа
            return
            
        # Обычная обработка операторов
        if expression and expression[-1] == ')':
            # Если выражение заканчивается скобкой - добавляем оператор
            expression += op
            current_input = "0"
        elif current_input != "0" and current_input != "-":
            # Если есть текущее число - добавляем его и оператор к выражению
            expression += current_input + op
            current_input = "0"
        elif expression and expression[-1] in ['+', '-', '*', '/', '^']:
            # Заменяем последний оператор на новый
            expression = expression[:-1] + op
        else:
            # Просто добавляем оператор к выражению
            expression += op

def handle_equals():
    """Обрабатывает вычисление выражения (=)"""
    global current_input, expression, reset_on_next_input, result
    
    # Если есть выражение или текущий ввод не "0"
    if (expression or current_input != "0") and current_input != "Error":
        full_expression = expression  # Начинаем с основного выражения
        
        # Добавляем текущее число к выражению
        if current_input != "0" or (expression and expression[-1] in ['+', '-', '*', '/', '^', '(']):
            full_expression += current_input
        
        # Вычисляем результат с помощью нашего парсера
        calculated_result = evaluate_expression(full_expression)
        
        # Округляем результат для красивого отображения
        calculated_result = round_result(calculated_result)
            
        result = calculated_result  # Сохраняем результат
        # expression сохраняем для отображения в верхней строке
        reset_on_next_input = True  # Следующий ввод начнет новое выражение

def handle_percent():
    """ПРОСТАЯ РЕАЛИЗАЦИЯ ПРОЦЕНТА: x% = x / 100 (вариант A)"""
    global current_input, reset_on_next_input, result
    try:
        value = float(current_input)  # Преобразуем текущий ввод в число
        # Просто делим на 100 - это самый понятный и надежный способ
        current_input = str(round_result(value / 100.0))
        reset_on_next_input = True
        result = current_input  # Показываем результат
    except:
        current_input = "Error"  # В случае ошибки (например, нечисловой ввод)
        reset_on_next_input = False

def handle_power():
    """Обрабатывает возведение в степень (^)"""
    global reset_on_next_input, result
    reset_on_next_input = False
    result = ""  # Сбрасываем результат
    handle_operation('^')  # Используем общую функцию для операций

def handle_parenthesis(parenthesis):
    """Обрабатывает ввод скобок"""
    global current_input, expression, reset_on_next_input, result
    
    reset_on_next_input = False
    result = ""  # Сбрасываем результат
    
    if parenthesis == '(':
        # Открывающая скобка
        if current_input != "0" and current_input != "Error":
            # Если есть текущее число - добавляем умножение перед скобкой
            expression += current_input + '*'
            current_input = "0"
        expression += '('  # Добавляем открывающую скобку
    else:
        # Закрывающая скобка
        if current_input != "0" and current_input != "Error":
            # Если есть текущее число - добавляем его и закрываем скобку
            expression += current_input + ')'
            current_input = "0"
        elif expression and expression[-1] == '(':
            # Нельзя закрыть пустую скобку - ошибка
            current_input = "Error"
        else:
            # Просто добавляем закрывающую скобку
            expression += ')'

def handle_shift():
    """Переключает между базовым и научным режимом"""
    global shift_mode, reset_on_next_input
    shift_mode = not shift_mode  # Инвертируем режим
    reset_on_next_input = False

def handle_menu():
    """Открывает/закрывает главное меню"""
    global menu_mode, menu_position, reset_on_next_input
    menu_mode = not menu_mode  # Инвертируем состояние меню
    menu_position = 0  # Сбрасываем позицию в меню на первую
    reset_on_next_input = False

def handle_scientific_function(func):
    """Обрабатывает научные функции (sin, cos, tan, log, и т.д.)"""
    global current_input, reset_on_next_input, result, expression
    
    try:
        # ОСОБАЯ ОБРАБОТКА ДЛЯ КОНСТАНТ pi и e
        if func in ['pi', 'e']:
            # Для констант создаем выражение вида "pi" или "e"
            expression = func
            if func == 'pi':
                result = "3.14159265359"  # 13 знаков (укороченный pi)
            elif func == 'e':
                result = "2.71828182846"  # 12 знаков (укороченный e)
            reset_on_next_input = True
            current_input = "0"  # Сбрасываем ввод
            return
            
        # Для остальных функций преобразуем текущий ввод в число
        input_value = current_input
        if current_input == "0" or current_input == "" or current_input == "-":
            value = 0  # Если ввод пустой или "0", используем 0
            input_value = "0"
        else:
            value = float(current_input)  # Преобразуем в число
            
        calculated_result = None  # Здесь будет результат вычисления
        
        # Создаем выражение для отображения в верхней строке
        if func == 'sin':
            expression = f"sin({input_value})"  # Синус угла в градусах
            calculated_result = math.sin(math.radians(value))  # Переводим в радианы и вычисляем
        elif func == 'cos':
            expression = f"cos({input_value})"  # Косинус угла в градусах
            calculated_result = math.cos(math.radians(value))
        elif func == 'tan':
            expression = f"tan({input_value})"  # Тангенс угла в градусах
            calculated_result = math.tan(math.radians(value))
        elif func == 'log':
            expression = f"log({input_value})"  # Десятичный логарифм
            calculated_result = math.log10(value) if value > 0 else float('nan')  # Только для положительных чисел
        elif func == 'ln':
            expression = f"ln({input_value})"  # Натуральный логарифм
            calculated_result = math.log(value) if value > 0 else float('nan')  # Только для положительных чисел
        elif func == 'sqrt':  # ИЗМЕНИЛИ 'sqr' на 'sqrt' для ясности
            expression = f"sqrt({input_value})"  # Квадратный корень
            calculated_result = math.sqrt(value) if value >= 0 else float('nan')  # Только для неотрицательных
        elif func == '!':
            expression = f"fact({input_value})"  # Факториал
            # ДОБАВИЛИ ОГРАНИЧЕНИЕ: факториал только для целых чисел от 0 до 20
            if value >= 0 and value == int(value) and value <= 20:
                calculated_result = math.factorial(int(value))
            else:
                result = "Error"  # Ошибка для дробных, отрицательных или слишком больших чисел
                return
        elif func == '1/x':
            expression = f"1/({input_value})"  # Обратная величина
            if value != 0:
                calculated_result = 1 / value
            else:
                result = "Error"  # Деление на ноль
                return
        elif func == 'x²':
            expression = f"({input_value})²"  # Квадрат числа
            calculated_result = value ** 2
        elif func == 'x³':
            expression = f"({input_value})³"  # Куб числа
            calculated_result = value ** 3
        elif func == '±':
            expression = f"-({input_value})"  # Смена знака
            calculated_result = -value
        
        # Если вычисление прошло успешно
        if calculated_result is not None:
            # Проверяем на NaN (Not a Number)
            if calculated_result != calculated_result:  # Особенность NaN: он не равен самому себе
                result = "Error"
            else:
                result = str(round_result(calculated_result))  # Округляем и преобразуем в строку
            reset_on_next_input = True
            current_input = "0"  # Сбрасываем ввод для следующей операции
            
    except Exception as e:
        result = "Error"  # В случае любой ошибки
        reset_on_next_input = False

# ===== ОБРАБОТКА МЕНЮ =====
def handle_about_navigation():
    """Обрабатывает навигацию в режиме 'О программе'"""
    global about_page, about_mode, last_nav_action
    
    current_time = time.ticks_ms()
    # Защита от слишком быстрых нажатий (не чаще чем раз в 300 мс)
    if time.ticks_diff(current_time, last_nav_action) > 300:
        nav_keys = fast_scan_nav()  # Сканируем навигационные кнопки
        if 'up' in nav_keys:
            about_page = (about_page - 1) % len(about_pages)  # Предыдущая страница
            last_nav_action = current_time
        elif 'down' in nav_keys:
            about_page = (about_page + 1) % len(about_pages)  # Следующая страница
            last_nav_action = current_time
        elif 'enter' in nav_keys:
            about_mode = False  # Выход из режима "О программе"
            last_nav_action = current_time

def handle_menu_selection():
    """Обрабатывает выбор пункта в главном меню"""
    global menu_mode, about_mode, shift_mode, menu_position, about_page
    
    if menu_position == 0:
        # "Basic Calc" - базовый режим калькулятора
        shift_mode = False
        menu_mode = False
    elif menu_position == 1:
        # "Scientific" - научный режим калькулятора
        shift_mode = True
        menu_mode = False
    elif menu_position == 2:
        # "Settings" - настройки (пока не реализовано)
        menu_mode = False
    elif menu_position == 3:
        # "About" - информация о программе
        about_mode = True
        about_page = 0  # Начинаем с первой страницы

def handle_key_events():
    """Обрабатывает все события клавиатуры и навигации"""
    global pressed_keys_history, pressed_nav_history, menu_position, last_nav_action
    
    # Получаем текущие нажатые клавиши
    current_keys = set([key for _, _, key in stable_matrix_keys])
    current_nav = set(stable_nav_keys)

    # Находим новые нажатия (которые не были нажаты в предыдущем цикле)
    new_key_presses = current_keys - pressed_keys_history

    # Обработка в зависимости от текущего режима
    if about_mode:
        # Режим "О программе" - обрабатываем навигацию
        handle_about_navigation()
                
    elif menu_mode:
        # Режим меню - обрабатываем навигацию по меню
        current_time = time.ticks_ms()
        for nav in current_nav:
            # Защита от слишком быстрых нажатий
            if time.ticks_diff(current_time, last_nav_action) > 300:
                if nav == 'up':
                    menu_position = (menu_position - 1) % 4  # Вверх по меню
                    last_nav_action = current_time
                elif nav == 'down':
                    menu_position = (menu_position + 1) % 4  # Вниз по меню
                    last_nav_action = current_time
                elif nav == 'enter':
                    handle_menu_selection()  # Выбор текущего пункта
                    last_nav_action = current_time
                
    else:
        # ОСНОВНОЙ РЕЖИМ КАЛЬКУЛЯТОРА - обрабатываем нажатия клавиш
        for key in new_key_presses:
            if key in '0123456789':  # Цифры
                handle_digit_input(key)
            elif key == '.':  # Десятичная точка
                handle_decimal_point()
            elif key == 'C':  # Очистка
                handle_clear()
            elif key == 'BS':  # Backspace
                handle_backspace()
            elif key in ['+', '-', '*', '/']:  # Основные операции
                handle_operation(key)
            elif key == '=':  # Вычисление
                handle_equals()
            elif key == '%':  # Проценты (ТЕПЕРЬ ПРОСТАЯ РЕАЛИЗАЦИЯ)
                handle_percent()
            elif key == '^':  # Степень
                handle_power()
            elif key in ['(', ')']:  # Скобки
                handle_parenthesis(key)
            elif key == 'SHIFT':  # Переключение режима
                handle_shift()
            elif key == 'MENU':  # Открытие меню
                handle_menu()
            else:
                # Все остальные клавиши - научные функции
                handle_scientific_function(key)

        # Обработка навигационных кнопок в основном режиме
        for nav in stable_nav_keys:
            if nav == 'enter':
                handle_equals()  # ENTER работает как =

    # Сохраняем текущее состояние для следующего цикла
    pressed_keys_history = current_keys
    pressed_nav_history = current_nav

# ===== ТАЙМЕР =====
def timer_irq(t):
    """Прерывание таймера - устанавливает флаг сканирования"""
    scan_flag[0] = 1

def init_keyboard_timer():
    """Инициализирует таймер для регулярного сканирования клавиатуры"""
    keyboard_timer = Timer(0)  # Создаем таймер 0
    keyboard_timer.init(period=50, mode=Timer.PERIODIC, callback=timer_irq)  # Период 50 мс
    return keyboard_timer

# ===== ГЛАВНАЯ ФУНКЦИЯ =====
def main():
    """Главная функция программы"""
    global display_tick
    
    # Выводим информацию о версии при запуске
    print("=" * 50)
    print("CALCULATOR v7.1 - FIXED CONSTANTS DISPLAY")
    print("=" * 50)
    print("UI Improvements:")
    print("- Shorter pi and e values for display") 
    print("- pi: 3.14159265359 (13 chars)")
    print("- e: 2.71828182846 (12 chars)") 
    print("- Fits perfectly on screen")
    print("=" * 50)
    print("KEY IMPROVEMENTS:")
    print("- Simple percent: x% = x/100")
    print("- Factorial limited to 0-20")
    print("- 'sqr' renamed to 'sqrt' for clarity")
    print("=" * 50)
    
    # Инициализируем таймер клавиатуры
    init_keyboard_timer()
    # Первоначальное обновление дисплея
    update_display()
    
    # Главный цикл программы
    while True:
        # Ждем флага сканирования от таймера
        if scan_flag[0] == 0:
            time.sleep_ms(1)  # Короткая пауза для экономии энергии
            continue

        scan_flag[0] = 0  # Сбрасываем флаг

        try:
            # Сканируем клавиатуру и навигационные кнопки
            current_matrix = fast_scan_matrix()
            current_nav = fast_scan_nav()
            # Устраняем дребезг контактов
            debounce_keys(current_matrix, current_nav)
            # Обрабатываем события клавиш
            handle_key_events()
            
            # Обновляем дисплей каждые 3 цикла (примерно 150 мс)
            display_tick += 1
            if display_tick >= 3:
                update_display()
                display_tick = 0
                
        except Exception as e:
            print(f"Error: {e}")  # Выводим ошибки в консоль
            time.sleep_ms(50)  # Защита от забивания консоли при бесконечных ошибках

# Запуск программы при непосредственном выполнении файла
if __name__ == "__main__":
    main()
