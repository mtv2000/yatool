## ya gen-config

Команда `ya gen-config` используется для генерации конфигурационного файла инструмента `ya`. Это позволяет пользователю создать стандартный (базовый) конфигурационный файл, содержащий описание и закомментированные значения по умолчанию для различных настроек. Пользователь может затем настроить файл конфигурации в соответствии со своими требованиями.

### Использование

`ya gen-config [OPTION]… [ya.conf]…`

- `ya gen-config path_proect/${USER}/ya.conf` генерирует пользовательский конфигурационный файл в указанном месте. Если конфигурация уже существует, новая конфигурация сохраняет и учитывает ранее заданные параметры.

- Если пользователь поместит конфигурацию в свой домашний каталог с именем `ya.conf`, она будет автоматически использоваться для определения параметров работы `ya`.

- Значения в `ya.conf` имеют наименьший приоритет и могут быть переопределены через переменные окружения или аргументы командной строки.

- Если каталог проекта (`path_proect`) отсутствует, можно сохранить конфигурацию в `~/.ya/ya.conf`.

### Опции

- `-h`, `--help` - Показать справку по использованию команды. Используйте `-hh` для вывода дополнительных опций и `-hhh` для ещё более расширенной помощи.
- `--dump-defaults` - Выгрузить значения по умолчанию в формате `JSON`

### Формат `ya.conf`

Файл `ya.conf` должен быть в формате [toml](https://github.com/toml-lang/toml). 

Важные указания для управления этим файлом:

- Для опций без параметров следует указывать `true` в качестве значения.
- Для опций, представляющих собой "словари" (например, `flags`), необходимо открыть соответствующую секцию (таблицу). В этой секции указываются записи в формате `key = "value"`.

#### Основные секции конфигурационного файла ya.conf

| Опция | Значение по умолчанию | Примечания |
|-------|---|----------------------------------------------------|
| auto_exclude_symlinks | false | Автоматически исключать симлинки |
| copy_shared_index_config | false | Копировать конфигурацию Shared Index |
| detect_leaks_in_pytest | true | Обнаруживать утечки в Pytest |
| directory_based | true | Создавать проект в файловой структуре |
| eager_execution | false | Быстрое выполнение |
| exclude_dirs | [] | Исключить каталоги |
| external_content_root_modules | [] | Добавить модули внешнего контента |
| fail_maven_export_with_tests | false | Завершать экспорт Maven с тестами при ошибке |
| generate_tests_for_deps | false | Генерировать тесты для зависимостей |
| generate_tests_run | false | Генерировать тестовые конфигурации Junit |
| idea_files_root | "None" | Корневая директория для .ipr и .iws файлов |
| idea_jdk_version | "None" | Версия JDK для проекта IDEA |
| iml_in_project_root | false | Хранить .iml файлы в корне проекта |
| iml_keep_relative_paths | false | Сохранять относительные пути в .iml файлах |
| minimal | false | Минимальный набор настроек проекта |
| oauth_exchange_ssh_keys | true | Обмен oauth-ключами SSH |
| oauth_token_path | "None" | Путь к файлу oauth токена |
| omit_test_data | false | Исключить test_data |
| omitted_test_statuses | ["good", "xfail", "not_launched"] | Cтатусы тестов, которые нужно пропустить |
| project_name | "None" | Имя проекта IDEA |
| regenarate_with_project_update | "None" | Перегенерация вместе с обновлением проекта |
| run_tests_size | 1 | Размер тестов по умолчанию для выполнения (1 - маленькие, 2 - маленькие+средние, 3 - все) |
| separate_tests_modules | false | Не объединять модули тестов с их библиотеками |
| setup_pythonpath_env | true | Настроить переменную окружения PYTHONPATH |
| strip_non_executable_target | "None" | Удалить неисполняемые цели |
| test_fakeid | "" | Идентификатор поддельного теста |
| use_atd_revisions_info | false | Использовать информацию о ревизиях ATD |
| use_command_file_in_testtool | false | Использовать командный файл в инструментарии для тестов |
| use_jstyle_server | false | Использовать сервер Jstyle |
| use_throttling | false | Использовать ограничение скорости |
| with_common_jvm_args_in_junit_template | false | Добавить общие флаги JVM_ARGS в шаблон Junit |
| with_content_root_modules | false | Генерировать модули корневого содержимого |
| with_long_library_names | false | Генерировать длинные имена библиотек |
| ya_bin3_required | "None" | Требуется ya_bin3 |

В файле `ya.conf` представлены различные параметры, которые можно настроить для управления процессом сборки, тестирования, кэшированием и другими аспектами работы с проектом.

К сожалению, сейчас нет удобного инструмента для того, чтобы определить, что делает тот или иной параметр. В будущем мы планируем добавить описания для параметров конфигурации и сделать работу с ними прозрачней.

Пока для того, чтобы настроить нужный аспект работы `ya` через файл конфигурации нужно:
- Найти аргумент в исходном коде (например `-j`, он будет обёрнут в класс `*Consumer`)
- Найти переменную, которая выставляется с помощью аргумента, обычно это `*Hook` (в данном случае `build_threads`)
- Найти соответствующий `ConfigConsumer`, это и будет нужное название параметра

Конфигурационный файл можно настроить под конкретные нужды проекта, активировав или деактивировав определенные функции, чтобы оптимизировать процесс разработки и сборки. 

### Порядок применения опций

Порядок применения опций для настройки инструментария ya описывает иерархию и логику переопределения настроек конфигураций, которые используются при работе с системой сборки.

Опции `ya`, указанные в файлах конфигурации или переданные через командную строку, применяются в следующем порядке, где каждый последующий уровень может переопределять настройки предыдущего.

Вот возможные места:

1. `$path_proect/ya.conf` - общие настройки для проекта.
2. `$path_proect/${USER}/ya.conf` - пользовательские настройки в рамках одного проекта.
3. `$repo/../ya.conf` - если требуется иметь разные настройки для разных репозиториев.
4. `~/.ya/ya.conf` - глобальные пользовательские настройки на уровне системы.
5. Переменные окружения.
6. Аргументы командной строки.

### Возможности именования `ya.conf`

Файлы конфигурации могут иметь специализированные имена, которые позволяют менять настройки в зависимости от конкретной системы или команды:

- `ya.conf` - базовый файл конфигурации.
- `ya.${system}.conf` - для конкретной операционной системы.
- `ya.${command}.conf` - для конкретной команды.
- `ya.${command}.${system}.conf` - для конкретной команды под конкретной операционной системе.

Модификаторы `${system}` и `${command}` адресуют конфигурационные файлы к определенной системе или команде, например, `ya.make.darwin.conf` для команды `ya make` на системе `darwin`.

## Примеры опций для конкретных команд `ya`

### Глобальные настройки и локальные переопределения
```
project_output = "/default/path"

[ide.qt]
project_output = "/path/to/qt/project"

[ide.msvs]
project_output = "c:\path\to\msvs\project"
```
В приведенном примере задается общий путь до проекта как `"/default/path"`, однако для команд `ya ide qt` и `ya ide msvs` устанавливаются специализированные пути.

### Переопределение словарных опций
```
[flags]
NO_DEBUGINFO = "yes"

[dump.json-test-list.flags]
MY_SPECIAL_FLAG = "yes"
```
Здесь для большинства сценариев используется флаг `NO_DEBUGINFO="yes"`, но для команды `ya dump json-test-list` задается дополнительный флаг `MY_SPECIAL_FLAG="yes"`, в то время как `NO_DEBUGINFO` не применяется.

## Подстановка переменных окружения

Строковые ключи могут указывать переменные окружения в формате `${ENV_VAR}`, которые будут подменяться после загрузки конфигов.

## Настройка цветов

`ya` использует систему маркировки текста с применением переменных окружения для управления цветовой схемой в терминале. Это позволяет пользователям менять настройки цветового отображения различных элементов терминала для улучшения читаемости и визуального восприятия.

```
alt1 = "cyan"
alt2 = "magenta"
alt3 = "light-blue"
bad = "red"
good = "green"
imp = "light-default"
path = "yellow"
unimp = "dark-default"
warn = "yellow"
```
Для изменения цветов, связанных с этими маркерами, можно использовать секцию `terminal_profile` в конфигурационном файле `ya.conf`. Это позволяет задать пользовательские цвета для каждого из маркеров.

### Пример конфигурационного файла:
```
[terminal_profile]
bad = "light-red"
unimp = "default"
```
В примере выше, цвет для маркера `bad` изменен на `light-red` (светло-красный), а для `unimp` используется цвет по умолчанию.

Чтобы добавить интересующие целевые платформы, достаточно несколько раз описать следующую конструкцию:
```
[[target_platform]]
platform_name = "default-darwin-arm64"
build_type = "relwithdebinfo"

[target_platform.flags]
ANY_FLAG = "flag_value"
ANY_OTHER_FLAG = "flag_value"
```
На каждый параметр командной строки `--target-platform-smth` существует аналогичный ключ для файла конфигурации.

## Описание дополнительных опций (alias)

Alias в `ya` позволяет объединять часто используемые аргументы в единое короткое обозначение, облегчая выполнение повторяющихся задач и упрощая командные вызовы. Это особенно полезно, когда нужно постоянно задавать одни и те же аргументы в командах сборки `ya make`.

Alias-ы описываются в конфигурационных файлах с использованием синтаксиса TOML Array of Tables. Это позволяет группировать настройки и легко применять их при необходимости.

### Примеры использования Alias

#### Добавление .go файлов

Для добавления симлинков на сгенерированные .go файлы в обычном режиме необходимо указать множество аргументов:
```bash
ya make path/to/project --replace-result --add-result=.go --no-output-for=.cgo1.go --no-output-for=.res.go --no-output-for=_cgo_gotypes.go --no-output-for=_cgo_import.go
```

##### Конфигурация alias-а в ya.make.conf:
```bash
# path_proect/<username>/ya.make.conf
replace_result = true  # --replace-result
add_result_extend = [".go"]  # --add-result=.go
suppress_outputs = [".cgo1", ".res.go", "_cgo_gotypes.go"]  # --no-output-for options
```
##### Создание alias-а в ya.conf:

```bash
# path_proect/<username>/ya.conf

[[alias]]
replace_result = true
add_result_extend = [".go"]
suppress_outputs = [".cgo1", ".res.go", "_cgo_gotypes.go"]

[alias._settings.arg]
names = ["–add-go-result"]
help = "Add generated .go files"
visible = true
```
Такой alias позволяет заменить длинную команду на:
`ya make path/to/project --add-go-result`

#### Отключение предпостроенных тулов

Для отключения использования предпостроенных тулов в обычном режиме нужны следующие аргументы:

`ya make path/to/project -DUSE_PREBUILT_TOOLS=no --host-platform-flag=USE_PREBUILT_TOOLS=no`

Описание желаемого поведения пропишем в `ya.conf`:
```
[host_platform_flags]
USE_PREBUILT_TOOLS = "no"

[flags]
USE_PREBUILT_TOOLS = "no"
```
Теперь опишем alias, который будет включаться по аргументу, переменной окружения или выставлением значения в любом `ya.conf`:
```
[[alias]]
[alias.host_platform_flags]
USE_PREBUILT_TOOLS = "no"

[alias.flags]
USE_PREBUILT_TOOLS = "no"

[alias._settings.arg]
names = ["-p", "–disable-prebuild-tools"]
help = "Disable prebuild tools"
visible = true

[alias._settings.env]
name = "YA_DISABLE_PREBUILD_TOOLS"

[alias._settings.conf]
name = "disable_prebuild_tools"
```
Теперь для активации поведения можно использовать один из следующих способов:
```bash
# Длинный аргумент:
  `ya make path/to/project --disable-prebuild-tools`
# Короткий аргумент:
  `ya make path/to/project -p`
# Переменная окружения:
  `YA_DISABLE_PREBUILD_TOOLS=yes ya make path/to/project`
# Значение в конфиге:
  echo "\ndisable_prebuild_tools=true\n" >> path_proect/$USER/ya.conf
  ya make path/to/project
```
## Работа с несколькими Alias-ами

Alias-ы в `ya` предлагают гибкий способ для упрощения и автоматизации командных вызовов, предоставляя возможность группировать часто используемые аргументы. Эта возможность не ограничивается лишь одним alias-ом или одним файлом, а позволяет создавать и применять множество alias-ов, разбросанных по различным файлам конфигурации. При этом alias-ы из разных файлов дополняют друг друга, а не перезаписывают настройки.

### Множественные Alias-ы

Можно создавать любое количество alias-ов, включая их в один или несколько файлов конфигурации. Это обеспечивает значительную гибкость в настройке среды разработки.

Alias-ы, определенные в разных файлах, не конфликтуют и не заменяют друг друга, что позволяет комбинировать различные конфигурационные файлы без риска потери настроек.

#### Пример с множественными файлами
```
# path/to/first/ya.conf
some_values = true

third_alias = true

[[alias]]
# ...
[alias._settings.conf]
name = "first_alias" 

[[alias]]
# ...

# path/to/second/ya.conf
some_other_values = true
[[alias]]
# ...
[alias._settings.conf]
name = "third_alias"

[[alias]]
first_alias = true
# ...

```
В этом примере, конфигурации alias-ов из двух разных файлов будут успешно применены и не повлияют друг на друга отрицательно.

### Пример с использованием target_platform
```
[[alias]]

[[alias.target_platform]]  # --target-platform
platfom_name = "..."
build_type = "debug"  # --target-platform-debug
run_tests = true  # --target-platform-tests
target_platform_compiler = "c_compiler"  # --target-platform-c-compiler
# ...
[alias.target_platform.flags]  # --target-platform-flag
FLAG = true
OTHER_FLAG = "other_value"

[alias._settings.arg]  # Create argument consumer for alias
names = ["-a", "--my-cool-alias"]  # Short and long name
help = "This alias are awesome! It really helps me"  # Help string
visible = true  # make it visible in `ya make --help` 
[alias._settings.env]  # Create environment consumer for alias, must starts with YA
name = "YA_MY_COOL_ALIAS"
[alias._settings.conf]  # Create config consumer for alias, can be enabled from any config-file
name = "my_cool_alias"
```

## Семантика Alias-ов

Внутри одного блока `[[alias]]` можно задавать произвольное количество опций и подопций.

### Создание аргумента или переменной окружения

Для добавления аргумента или переменной окружения, используются ключи `[alias._settings.arg]` и `[alias._settings.env]`. Определенные таким образом настройки становятся доступными во всех подкомандах ya.

Для создания опции, которая будет существовать только в конкретной команде (например `make`), достаточно дописать между ключами `alias` и `settings` произвольный префикс:

- `[alias.make._settings.args]` – будет активно только для ya make ...
- `[alias.ide.idea._settings.args]` – работает только для ya ide idea ...

### Включение через конфигурационный файл

Ключ `[alias._settings.conf]` позволяет включить определенный alias через любой конфигурационный файл. Это добавляет уровень гибкости, позволяя активировать alias, даже если он описан в файле, который применяется раньше по порядку обработки.

Таким образом, появляется возможность применять один alias внутри другого, обеспечивая таким образом простейшую композицию.

## Композиция

Если возникла необходимость вынести общую часть из alias-ов, можно воспользоваться композицией.
Пусть у нас есть два alias-а:
```
[[alias]]
first_value = 1
second_value = 2
[[alias._settings.arg]]
names = ["--first"]

[[alias]]
second_value = 2
third_value = 3
[[alias._settings.arg]]
names = ["--second"]
```
Чтобы вынести общую часть, нужно создать новый alias c параметром конфигурации:
```
[[alias]]
second_value = 2
[[alias._settings.conf]]
name = "common_alias"

[[alias]]
first_value = 1
common_alias = true  # Call alias
[[alias._settings.arg]]
names = ["--first"]

[[alias]]
common_alias = true  # Call alias
third_value = 3
[[alias._settings.arg]]
names = ["--second"]
```
Теперь, при вызове `ya <команда> --second` применится alias `common_alias`, и выставится значение для `third_value`.

Особенности:

- Можно вызывать несколько alias-ов внутри другого alias-а
- Глубина «вложенности» может быть любой
- Есть защита от циклов
- Можно использовать alias, объявленный позже места использования или находящийся в другом файле

