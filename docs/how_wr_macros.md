## Основные принципы по написанию макросов.

Макросы используются для создания повторно используемых блоков кода, которые выполняют определенные задачи, такие как настройка модулей, установка переменных, отключение функциональности и многое другое. 

Определение макроса осуществляется посредством ключевого слова `macro`, за которым следует имя макроса. Макрос может также принимать параметры, которые указываются в скобках сразу после его имени.

Пример:
```plaintext
macro MY_MACRO(PARAM1, PARAM2) {
   // Код макроса
 }
```
Установка переменных и вызов функций внутри макроса осуществляется следующим образом: переменные устанавливаются при помощи функции `SET`, а для выполнения определённых действий можно вызывать другие функции.

Пример:
```plaintext
   macro SET_VARIABLES() {
       SET(VAR1 "value1")
       SET(VAR2 "value2")
   }
```
Условия в макросах могут быть заданы для выполнения действий в зависимости от значений переменных. Эти условия определяются с помощью ключевого слова `when` и проверяются на истинность.

Пример:
```plaintext
   macro CONDITIONAL_SET(CONDITION) {
       when ($CONDITION == "yes") {
           SET(VAR "value1")
       }
       otherwise {
           SET(VAR "value2")
       }
   }
```
Отключение функциональности в макросах осуществляется с использованием функции `DISABLE` для отключения определённых функций или зависимостей, а включение осуществляется с помощью функции `ENABLE`.

Пример:
   ```plaintext
### @usage: WERROR()
### Consider warnings as errors in the current module.
### In the bright future will be removed, since WERROR is the default.
### Priorities: NO_COMPILER_WARNINGS > NO_WERROR > WERROR_MODE > WERROR.
macro WERROR() {
    ENABLE(WERROR)
}

### @usage: NO_WERROR()
### Override WERROR() behavior
### Priorities: NO_COMPILER_WARNINGS > NO_WERROR > WERROR_MODE > WERROR.
macro NO_WERROR() {
    DISABLE(WERROR)
}
```
Макросы могут использовать глобальные переменные и атрибуты, которые влияют на поведение всего проекта.

Пример:
```plaintext
   macro SET_GLOBAL_ATTRIBUTES() {
       .GLOBAL=_AARS _PROGUARD_RULES
   }
```
