## krevedko

## Как описывать тесты для языков

### C++

Сейчас поддержаны два тестовых фреймворка:
* [unittest](https://a.yandex-team.ru/arc/trunk/arcadia/library/cpp/testing/unittest) - собственная разработка
* [gtest](https://github.com/google/googletest) - популярное решение от Google

Также есть отдельная библиотека [library/cpp/testing/common](https://a.yandex-team.ru/arc/trunk/arcadia/library/cpp/testing/common), в которой находятся полезные утилиты, независящие от фреймворка.

**Бенчмарки:** Используется библиотека [google benchmark](https://a.yandex-team.ru/arc/trunk/arcadia/contrib/libs/benchmark/README.md) и модуль `G_BENCHMARK`. Все подключенные к автосборке бенчмарки запускаются в CI по релевантным коммитам и накапливают историю метрик.

**Fuzzing:** Фаззинг - это техника тестирования, заключающаяся в передаче приложению на вход неправильных, неожиданных или случайных данных. Все подробности [здесь](fuzzing).

**Linting:** Поддержан статический анализ файлов с помощью `clang-tidy`. Подробнее про подключение своего проекта к линтингу в автосборке можно прочитать [здесь](style#clang-tidy).

**Метрики:** Помимо метрик от бенчмарков также можно сообщать числовые метрики из `UNITTEST()` и `GTEST()`. Для добавления метрик используйте функцию `testing::Test::RecordProperty` если работаете с `gtest`, или макрос `UNIT_ADD_METRIC` если работаете с `unittest`.

{% list tabs %}

- Gtest

  ```cpp
  TEST(Solver, TrivialCase) {
      // ...
      RecordProperty("num_iterations", 10);
      RecordProperty("score", "0.93");
  }
  ```
- Unittest

  ```cpp
  Y_UNIT_TEST_SUITE(Solver) {
      Y_UNIT_TEST(TrivialCase) {
          // ...
          UNIT_ADD_METRIC("num_iterations", 10);
          UNIT_ADD_METRIC("score", 0.93);
      }
  }
  ```

{% endlist %}

---

Минимальный `ya.make` для тестов выглядит так:

```
UNITTEST() | GTEST() | G_BENCHMARK()

OWNER(...)

SRCS(tests.cpp)

END()
```

Подробная документация о тестах на C++ расположена [здесь](cpp).

### Python

Основным фреймворком для написания тестов на Python является [pytest](https://pytest.org/).

Поддерживаются Python 2 (модуль `PY2TEST`), Python 3 (модуль `PY3TEST`) и модуль `PY23_TEST`. Все тестовые файлы перечисляются в макросе `TEST_SRCS()`.

Для работы с файлами, внешними программами, сетью в тестах следует использовать специальную библиотеку [yatest](https://a.yandex-team.ru/arc/trunk/arcadia/library/python/testing/yatest_common).

**Метрики**: Чтобы сообщить метрики из теста, необходимо использовать funcarg metrics.
```python
def test(metrics):
    metrics.set("name1", 12)
    metrics.set("name2", 12.5)
```

**Бенчмарки**: Для бенчмарков следует использовать функцию `yatest.common.execute_benchmark(path, budget=None, threads=None)`. Чтобы результаты отображались в CI, результаты нужно записывать в метрики.

**Канонизация**: Можно канонизировать простые типы данных, списки, словари, файлы и директории. Тест сообщает о данных, которые нужно сравнить с каноническими, через возврат их из тестовой функции командой return.

**Linting**: Все python файлы, используемые в сборке и тестах, подключаемые через `ya.make` в секциях `PY_SRCS()` и `TEST_SRCS()`, автоматически проверяются `flake8` линтером.

**Python imports**: Для программ `PY2_PROGRAM`, `PY3_PROGRAM`, `PY2TEST`, `PY3TEST`, `PY23_TEST`, собранных из модулей на питоне, добавлена проверка внутренних модулей на их импортируемость - `import_test`. Это позволит обнаруживать на ранних стадиях конфликты между библиотеками, которые подключаются через `PEERDIR`, а также укажет на неперечисленные в `PY_SRCS` файлы (но не `TEST_SRCS`).

Подробная документация о тестах на Python расположена [здесь](python).

### Java

Для тестов используется фреймворк [JUnit](https://junit.org/junit5/) версий 4.x и 5.x.

Тестовый модуль для JUnit4 описывается модулем `JTEST()` или `JTEST_FOR(path/to/testing/module)`.
* `JTEST()`: система сборки будет искать тесты в `JAVA_SRCS()` данного модуля.
* `JTEST_FOR(path/to/testing/module)`: система сборки будет искать тесты в тестируемом модуле.

Для включения JUnit5 вместо `JTEST()` необходимо использовать `JUNIT5()`.

Содержание `ya.make` файла для `JUNIT5()` и `JTEST()` отличается только набором зависимостей.

Минимальный `ya.make` файл выглядит так:

{% list tabs %}

- JUnit4

  ```
  JTEST()

  JAVA_SRCS(FileTest.java)

  PEERDIR(
    # Сюда же необходимо добавить зависимости от исходных кодов вашего проекта
    contrib/java/junit/junit/4.12 # Сам фреймворк JUnit 4
    contrib/java/org/hamcrest/hamcrest-all # Можно подключить набор Hamcrest матчеров
  )

  END()
  ```
- JUnit5
  ```
  JUNIT5()
  JAVE_SRCS(FileTest.java)
  PEERDIR(
    # Сюда же необходимо добавить зависимости от исходных кодов вашего проекта
    contrib/java/org/junit/jupiter/junit-jupiter # Сам фреймворк JUnit 5
    contrib/java/org/hamcrest/hamcrest-all # Набор Hamcrest матчеров
  )
  END()
  ```

{% endlist %}

**Java classpath clashes**: Есть возможность включить автоматическую проверку на наличие нескольких одинаковых классов в [Java Classpath](https://en.wikipedia.org/wiki/Classpath). В проверке участвует не только имя класса, но и хэш-сумма файла с его исходным кодом, так как идентичные классы из разных библиотек проблем вызывать не должны. Для включения этого типа тестов в ya.make файл соответствующего проекта нужно добавить макрос `CHECK_JAVA_DEPS(yes)`.

**Linting**: На все исходные тексты на Java, которые подключены в секции `JAVA_SRCS`, включён статический анализ. Для проверки используется утилита [checkstyle](https://checkstyle.org/).

**Канонизация**: Для работы с канонизированными данными используйте функции из [devtools/jtest](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/jtest).

Подробная документация о тестах на Java расположена [здесь](java).

### Go

Тесты работают поверх [стандартного тулинга для Go](https://pkg.go.dev/testing). Для работы с зависимостями теста следует использовать библиотеку [`library/go/test/yatest`](https://a.yandex-team.ru/arc/trunk/arcadia/library/go/test/yatest/env.go).

Все тестовые файлы должны иметь суффикс `_test.go`. Они перечисляются в макросе `GO_TEST_SRCS`.

Тестовый модуль описывается модулем `GO_TEST()` или `GO_TEST_FOR(path/to/testing/module)`.
* `GO_TEST()`: система сборки будет искать тесты в `GO_TEST_SRCS()` данного модуля.
* `GO_TEST_FOR(path/to/testing/module)`: система сборки будет искать тесты в `GO_TEST_SRCS` в тестируемом модуле.

Минимальные `ya.make` файлы выглядят так:

{% list tabs %}

- GO_TEST()

  ```
  GO_TEST()

  GO_TEST_SRCS(file_test.go)

  END()
  ```
- GO_TEST_FOR()

  В `project/ya.make` в макросе `GO_TEST_SRCS` перечисляются тестовые файлы:

  ```
  GO_LIBRARY() | GO_PROGRAM()

  SRCS(file.go)

  GO_TEST_SRCS(file_test.go)

  END()

  RECURSE(tests)
  ```

  В `project/tests/ya.make` указывается относительный путь от корня аркадии на  тестируемый модуль через `GO_TEST_FOR`:

  ```
  GO_TEST_FOR(relative/path/to/project)

  END()
  ```

{% endlist %}

**Канонизация**: Для работы с такими тестами используйте [library/go/test/canon](https://a.yandex-team.ru/arc/trunk/arcadia/library/go/test/canon/canon.go). [Пример](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/ya/test/tests/canonize_new_format/canonize_file_with_diff_tool).

**Бенчмарки**: Чтобы включить бенчмарки в проекте, нужно добавить тэг `ya:run_go_benchmark` в `ya.make` проекта. [Пример](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/ya/test/tests/go/data/benchmark_fast).

Подробная документация о тестах на Go расположена [здесь](go).


# Тесты

Unit-тесты в Аркадии оформляются в виде отдельных целей со своим `ya.make`.
Для их запуска используется команда `ya make -t`.
Подробности есть в [документации ya][ya doc]; см. также: [`RECURSE_FOR_TESTS`].

Для написания тестов у нас имеется два фреймворка:
*unittest* (наша собственная разработка) и *gtest* (популярное решение от Google).
Также есть библиотека [`library/cpp/testing/common`],
в которой находятся полезные утилиты, не зависящие от фреймворка.

Поддержка gtest в Аркадии появилась недавно,
поэтому фреймворк не очень распространен.
Тем не менее, у него есть ряд преимуществ по сравнению с unittest:

- очень подробно выводится контекст, когда ломается тест;
- два семейства макросов для сравнения:
  `ASSERT` останавливает тест, `EXPECT` отмечает тест как проваленный,
  но не останавливает его, давая возможность выполнить остальные проверки;
- возможность расширять фреймворк с помощью механизма матчеров;
- можно использовать gmock (справедливости ради заметим,
  что gmock можно использовать и в unittest;
  однако в gtest он проинтегрирован лучше, а проекты уже давно объединены);
- можно сравнивать некоторые типы —
  и даже получать относительно понятное сообщение об ошибке —
  даже если не реализован `operator<<`;
- интеграция почти с любой IDE из коробки;
- фреймворк известен во внешнем мире, новичкам не нужно объяснять, как писать тесты;
- есть поддержка fixtures (в unittest тоже есть, но имеет существенные недостатки реализации);
- есть поддержка параметрических тестов
  (один и тот же тест можно запускать с разными значениями входного параметра);
- можно использовать в open-source проектах.

К недостаткам gtest можно отнести:

- отсутствие поддержки аркадийных стримов.
  Впрочем, для популярных типов из `util` мы сделали собственные реализации `PrintTo`;
- отсутствие макроса, проверяющего, что код бросает ошибку с данным сообщением.
  Мы сделали такой макрос сами, а также добавили несколько полезных матчеров;

Четких рекомендаций по выбору фреймворка для тестирования нет —
руководствуйтесь здравым смыслом, обсудите с командой, взвесьте все «за» и «против».
Учитывайте, что при смене типа тестов с unittest на gtest
потеряется история запуска тестов в CI.
Впрочем, если ваши тесты не мигают (а мы очень на это надеемся),
история вам и не нужна.

## Gtest

Подробная документация по gtest доступна
[в официальном репозитории gtest][gtest doc] и [gmock][gmock doc].
Этот раздел дает лишь базовое представление о фреймворке,
а также описывает интеграцию gtest в Аркадию.

Для написания тестов с этим фреймворком используйте цель типа `GTEST`.
Минимальный `ya.make` выглядит так:

```yamake
GTEST()

OWNER(...)

SRCS(test.cpp ...)

END()
```

Поддерживаются стандартные для Аркадии настройки тестов:
`TIMEOUT`, `FORK_TESTS` и прочие.
Подробнее про это написано в [документации ya][ya doc].

Внутри `cpp` файлов с тестами импортируйте `library/cpp/testing/gtest/gtest.h`.
Этот заголовочный файл подключит gtest и наши расширения для него.
Для объявления тестов используйте макрос `TEST`.
Он принимает два параметра: название группы тестов (test suite)
и название конкретного теста.

{% note info %}

В аркадии своя реализация функции `main`, реализовывать ее не нужно. Для кастомизации своих тестов можно воспользоваться хуками из `library/cpp/testing/hook`.

{% endnote %}

Пример минимального `cpp` файла с тестами:

```cpp
#include <library/cpp/testing/gtest/gtest.h>

TEST(BasicMath, Addition) {
    EXPECT_EQ(2 + 2, 4);
}

TEST(BasicMath, Multiplication) {
    EXPECT_EQ(2 * 2, 4);
}
```

Для выполнения проверок в теле теста используйте специальные макросы.
Они, в отличие от стандартных `Y_ASSERT` и `Y_ABORT_UNLESS`,
умеют печатать развернутые сообщения об ошибках.
Например, `ASSERT_EQ(a, b)` проверит, что два значения равны;
в случае, если это не так, макрос отметит тест как проваленный и остановит его.

Каждый макрос для проверки имеет два варианта:
`ASSERT` останавливает тест, `EXPECT` — нет.
По-умолчанию используйте `EXPECT`,
так вы получите больше информации после запуска тестов.
Используйте `ASSERT` только если проверяете условие,
от которого зависит корректность дальнейшего кода теста:

```cpp
TEST(EtheriaHeart, Activate) {
    auto* result = NEtheria::Activate();

    // Если указатель нулевой, последующие проверки приведут к UB.
    ASSERT_NE(result, nullptr);

    EXPECT_EQ(result->Code, 0);
    EXPECT_EQ(result->ConnectedCrystals, 5);
    EXPECT_GE(result->MaxPower, 1.5e+44);
}
```

Полный список доступных макросов есть в
[официальной документации][gtest macros]
и [документации по продвинутым возможностям gtest][gtest advanced macros].

Также gtest позволяет добавить к каждой проверке пояснение.
Оно будет напечатано если проверка провалится.
Для форматирования пояснений используется `std::ostream`:

```cpp
TEST(LotrPlot, Consistency) {
    EXPECT_GE(RingIsDestroyed() - FrodoLeftHobbiton(), TDuration::Days(183))
        << "no, eagles were not an option because " << Reasons();
}
```

Для более сложных проверок предусмотрен механизм матчеров.
Например, проверим, что контейнер содержит элемент,
удовлетворяющий определенному условию:

```cpp
TEST(GtestMatchers, SetElements) {
    THashSet<TString> elements{"water", "air", "earth", "fire"};
    EXPECT_THAT(elements, testing::Contains("air"));
    EXPECT_THAT(elements, testing::Contains(testing::StrCaseEq("Fire")));
}
```

Наши [расширения][gtest custom matchers src] добавляют макрос для проверки сообщений в исключениях:

```cpp
TEST(YException, Message) {
    EXPECT_THROW_MESSAGE_HAS_SUBSTR(
        ythrow yexception() << "black garnet is not active",
        yexception,
        "not active");
```

Для тестирования кода, прекращающего выполнение приложения
(например, выполняющего `Y_ASSERT` или `Y_ABORT_UNLESS`),
используйте макросы
`EXPECT_DEATH`, `EXPECT_DEBUG_DEATH`, `ASSERT_DEATH`, `ASSERT_DEBUG_DEATH`:

```cpp
TEST(Vector, AccessBoundsCheck) {
    TVector<int> empty{};
    EXPECT_DEBUG_DEATH(empty[0], "out of bounds");
}
```

Матчер `NGTest::GoldenFileEq(filename)` описан в разделе [канонизация](canon#cpp-gtest-matcher).


## Unittest

Для написания тестов с этим фреймворком используйте цель типа `UNITTEST`.
Минимальный `ya.make` выглядит так:

```yamake
UNITTEST()

OWNER(...)

SRCS(test.cpp ...)

END()
```

Поддерживаются стандартные для Аркадии настройки тестов:
`TIMEOUT`, `FORK_TESTS` и прочие.
Подробнее про это написано в [документации ya][ya doc].

Внутри `cpp` файлов с тестами подключите `library/cpp/testing/unittest/registar.h`.

{% note warning %}

Не подключайте файл `library/cpp/testing/unittest/gtest.h` —
это deprecated интерфейс unittest, который пытается выглядеть как gtest.

{% endnote %}

Для объявления группы тестов используйте макрос `Y_UNIT_TEST_SUITE`.
Для объявления тестов внутри группы используйте макрос `Y_UNIT_TEST`.

Пример минимального `cpp` файла с тестами:

```cpp
#include <library/cpp/testing/unittest/registar.h>

Y_UNIT_TEST_SUITE(BasicMath) {
    Y_UNIT_TEST(Addition) {
        UNIT_ASSERT_VALUES_EQUAL(2 + 2, 4);
    }

    Y_UNIT_TEST(Multiplication) {
        UNIT_ASSERT_VALUES_EQUAL(2 * 2, 4);
    }
}
```

Для выполнения проверок в теле теста используйте специальные макросы:

| Макрос | Описание |
| ------ | -------- |
| **UNIT_FAIL**(*M*) | Отметить тест как проваленный и остановить его. |
| **UNIT_FAIL_NONFATAL**(*M*) | Отметить тест как проваленный но не останавливать его. |
| **UNIT_ASSERT**(*A*) | Проверить, что условие *A* выполняется. |
| **UNIT_ASSERT_EQUAL**(*A*, *B*) | Проверить, что *A* равно *B*. |
| **UNIT_ASSERT_UNEQUAL**(*A*, *B*) | Проверить, что *A* не равно *B*. |
| **UNIT_ASSERT_LT**(*A*, *B*) | Проверить, что *A* меньше *B*. |
| **UNIT_ASSERT_LE**(*A*, *B*) | Проверить, что *A* меньше или равно *B*. |
| **UNIT_ASSERT_GT**(*A*, *B*) | Проверить, что *A* больше *B*. |
| **UNIT_ASSERT_GE**(*A*, *B*) | Проверить, что *A* больше или равно *B*. |
| **UNIT_ASSERT_VALUES_EQUAL**(*A*, *B*) | Проверить, что *A* равно *B*. В отличие от `UNIT_ASSERT_EQUAL`, воспринимает `char*` как null-terminated строку, а также печатает значения переменных с помощью `IOutputStream` при провале проверки. |
| **UNIT_ASSERT_VALUES_UNEQUAL**(*A*, *B*) | Проверить, что *A* не равно *B*. В отличие от `UNIT_ASSERT_UNEQUAL`, воспринимает `char*` как null-terminated строку, а также печатает значения переменных с помощью `IOutputStream` при провале проверки. |
| **UNIT_ASSERT_DOUBLES_EQUAL**(*E*, *A*, *D*) | Проверить, что *E* и *A* равны с точностью *D*. |
| **UNIT_ASSERT_STRINGS_EQUAL**(*A*, *B*) | Проверить, что строки *A* и *B* равны. В отличие от `UNIT_ASSERT_EQUAL`, воспринимает `char*` как null-terminated строку. |
| **UNIT_ASSERT_STRINGS_UNEQUAL**(*A*, *B*) | Проверить, что строки *A* и *B* не равны. В отличие от `UNIT_ASSERT_UNEQUAL`, воспринимает `char*` как null-terminated строку. |
| **UNIT_ASSERT_STRING_CONTAINS**(*A*, *B*) | Проверить, что строка *B* является подстрокой в *A*. |
| **UNIT_ASSERT_NO_DIFF**(*A*, *B*) | Проверить, что строки *A* и *B* равны. Печатает цветной diff строк при провале проверки. |
| **UNIT_ASSERT_EXCEPTION**(*A*, *E*) | Проверить, что выражение *A* выбрасывает исключение типа *E*. |
| **UNIT_ASSERT_NO_EXCEPTION**(*A*) | Проверить, что выражение *A* не выбрасывает исключение. |
| **UNIT_ASSERT_EXCEPTION_CONTAINS**(*A*, *E*, *M*) | Проверить, что выражение *A* выбрасывает исключение типа *E*, сообщение которого содержит подстроку *M*. |

У каждого макроса `UNIT_ASSERT` есть версия `UNIT_ASSERT_C`,
позволяющая передать пояснение к проверке. Например:

```cpp
UNIT_ASSERT_C(success, "call should be successful");
UNIT_ASSERT_GT_C(rps, 500, "should generate at least 500 rps");
```


## Mock

Для реализации mock-объектов мы используем [gmock].
Если вы используете gtest, gmock подключен автоматически.
Если вы используете unittest, для подключения gmock нужно добавить `PEERDIR`
на [`library/cpp/testing/gmock_in_unittest`]
и импортировать файл `library/cpp/testing/gmock_in_unittest/gmock.h`.

## Доступ к зависимостям { #dependencies }

Если вы используете в своем **ya.make** [зависимости](https://docs.yandex-team.ru/devtools/test/dependencies), то обращаться к таким данным в коде теста нужно, используя библиотеку [library/cpp/testing](https://a.yandex-team.ru/arcadia/library/cpp/testing/common/env.h):

```cpp
#include <library/cpp/testing/common/env.h>

void ReadDependency() {
    // Путь до файла/директории из репозитория, описанных с помощью макроса DATA("arcadia/devtools/dummy_arcadia/cat/main.cpp")
    TString testFilePath = ArcadiaSourceRoot() + "/devtools/dummy_arcadia/cat/main.cpp";

    // Путь до Sandbox-ресурса, описанного макросом DATA(sbr://53558626) # test.txt
    TString sandboxResourcePath = GetWorkPath() + "/test.txt";

    // Путь до файла из DEPENDS("devtools/dummy_arcadia/cat")
    // Обратите внимание: путь в DEPENDS указывает до сборочной цели, а BinaryPath требует указания пути до файла
    TString binaryFilePath = BinaryPath("devtools/dummy_arcadia/cat/cat");
}
```

## Утилиты для тестирования
Все функции и утилиты, которые не зависят от тестового фреймворка распологаются в директории [common](https://a.yandex-team.ru/arc_vcs/library/cpp/testing/common)

- Получение сетевых портов в тестах:
  Для получения сетевого порта в тестах необходимо использовать функцию `NTesting::GetFreePort()` из [network.h](https://a.yandex-team.ru/arc_vcs/library/cpp/testing/common/network.h), которая вернет объект - владелец для порта. Порт будет считаться занятым до тех пор, пока владелец жив.
Во избежание гонок с выделением портов необходимо держать объект-владелец в течении всей жизни теста, или по крайней мере пока в тесте не запустится сервис, который вызовет `bind` на этом порту.

Пример использования:
```
#include <library/cpp/testing/common/network.h>

TEST(HttpServerTest, Ping) {
    auto port = NTesting::GetFreePort();
    auto httpServer = StartHttpServer("localhost:" + ToString(port));
    auto client = CreateHttpClient("localhost:" + ToString(port));
    EXPECT_EQ(200, client.Get("/ping").GetStatus());
}
```

- Функции для получения путей для корня аркадии и до корня билд директории в тестах.
  Все функции расположены в файле [env.h](https://a.yandex-team.ru/arc_vcs/library/cpp/testing/common/env.h) с описанием.

## Хуки для тестов
Хуки позволяют выполнять различные действия при старте или остановке тестовой программы.
Подробнее про использование можно прочитать в [README.md](https://a.yandex-team.ru/arc_vcs/library/cpp/testing/hook/README.md)


## Тесты с канонизацией вывода

Тесты с канонизацией вывода используются для регрессионного тестирования.
При первом запуске теста вывод тестируемой программы сохраняется,
при последующих запусках система проверяет, что вывод не изменился.

К сожалению, в C++ такие тесты в данный момент не поддерживаются.

За состоянием поддержки этой возможности можно следить в задаче [DEVTOOLS-1467].


## Параметры теста

Поведение тестов можно настраивать, передавая в них параметры.

При запуске тестов,
используйте ключ `--test-param` чтобы передать в тест пару ключ-значение.
Например: `ya make -t --test-param db_endpoint=localhost:1234`.

Для доступа к параметру из теста
используйте функцию `GetTestParam`:

```cpp
TEST(Database, Connect) {
    auto endpoint = GetTestParam("db_endpoint", "localhost:8080");
    // ...
}
```


## Метрики теста

Наш CI поддерживает возможность выгрузки из теста пользовательских метрик.
У каждой метрики есть название и значение — число с плавающей точкой.
CI покажет график значений метрик на странице теста.

Для добавления метрик
используйте функцию `testing::Test::RecordProperty` если работаете с gtest,
или макрос `UNIT_ADD_METRIC` если работаете с unittest.
Например, создадим метрики `num_iterations` и `score`:

{% list tabs %}

- Gtest

  ```cpp
  TEST(Solver, TrivialCase) {
      // ...
      RecordProperty("num_iterations", 10);
      RecordProperty("score", "0.93");
  }
  ```

  {% note warning %}

  `RecordProperty` принимает на вход целые числа и строки.
  Наш CI не умеет работать со строковыми значениями метрик,
  поэтому каждую строку он будет воспринимать как число.
  В случае, если строку не удастся преобразовать в число, тест упадет.

  {% endnote %}

- Unittest

  ```cpp
  Y_UNIT_TEST_SUITE(Solver) {
      Y_UNIT_TEST(TrivialCase) {
          // ...
          UNIT_ADD_METRIC("num_iterations", 10);
          UNIT_ADD_METRIC("score", 0.93);
      }
  }
  ```

{% endlist %}


[`RECURSE_FOR_TESTS`]: https://docs.yandex-team.ru/ya-make/manual/common/macros#recurse
[`library/cpp/testing/common`]: https://a.yandex-team.ru/arc/trunk/arcadia/library/cpp/testing/common
[`library/cpp/testing/gmock_in_unittest`]: https://a.yandex-team.ru/arc/trunk/arcadia/library/cpp/testing/gmock_in_unittest
[DEVTOOLS-1467]: https://st.yandex-team.ru/DEVTOOLS-1467
[ya doc]: https://docs.yandex-team.ru/ya-make/manual/tests/common
[gtest]: https://github.com/google/googletest
[gtest doc]: https://github.com/google/googletest/tree/main/docs
[gmock]: https://github.com/google/googletest/blob/master/googlemock/README.md
[gmock doc]: https://github.com/google/googletest/tree/master/googlemock/docs
[gtest macros]: https://github.com/google/googletest/blob/main/docs/primer.md#assertions
[gtest advanced macros]: https://github.com/google/googletest/blob/main/docs/advanced.md#more-assertions
[gtest custom matchers src]: https://a.yandex-team.ru/arc/trunk/arcadia/library/cpp/testing/gtest_extensions/matchers.h


# Тесты на Python

{% note info %}

Пример проекта на Python с использованием внешних зависимостей можно найти [здесь](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/examples/tests/using_py_library).

{% endnote %}

Основным фреймворком для написания тестов на Python является [pytest](https://pytest.org/). Поддерживаются Python 2 (макрос `PY2TEST`, считается устаревшим), Python 2/3 совместимые тесты (макрос `PY23_TEST`) и Python 3 (макрос `PY3TEST`). Типичный файл **ya.make** выглядит так:

```yamake
OWNER(g:my-group)

PY3TEST() # Используем pytest для Python 3 (PY2TEST будет означать Python 2)

PY_SRCS( # Зависимости тестов, например, абстрактный базовый класс теста
    base.py
)

TEST_SRCS( # Перечисление всех файлов с тестами
    test.py
)

SIZE(MEDIUM)

END()
```

Подробное описание всех возможностей фреймворка **pytest** можно почитать в [документации](https://docs.pytest.org/). Простейший тест выглядит следующим образом:

```python
# test.py
import logging
import pytest

logger = logging.getLogger("test_logger")

def test_one_1():
    logger.info("Info message")

def test_one_2():
    assert 1 == 2
```

Ниже перечислены некоторые особенности, которые следует учитывать при написании кода тестов:

* Имена тестовых классов должны начинаться на `Test`, в них не должно быть конструктора `__init__`.
* Имена тестовых методов / функций должны начинаться на `test`.
* pytest умеет показывать расширенную информацию при срабатывании assert, поэтому писать подробное сообщение об ошибке для assert обычно не надо.
* Если тесты рассчитывают на файл `base.py` или код в `__init__.py`, то их нужно явно перечислить в макросе `TEST_SCRS` или `PY_SRCS` (см. пример ya.make выше).
* Переменная [sys.executable](https://docs.python.org/3/library/sys.html#sys.executable), ссылается не на интерпретатор Python, а на исполняемый файл теста. Чтобы получить путь до интерпретатора, необходимо вызвать метод `yatest.common.python_path()`:
```python
import pytest
import yatest.common

def test_python_path():
    python_path = yatest.common.python_path()
    # ...
```
* Переменная тестового модуля `__file__` в общем случае не будет указывать на реальное местоположение файла с тестом. Подробнее о том, как получить путь до файла, описано в следующем разделе.

## Библиотека yatest { #yatest }

В едином репозитории код на Python (в том числе и код тестов) перед запуском собирается в исполняемую программу. Для того, чтобы работать с файлами, внешними программами, сетью и так далее, следует использовать специальную библиотеку [yatest](https://a.yandex-team.ru/arc/trunk/arcadia/library/python/testing/yatest_common). Некоторые полезные методы этой библиотеки приведены в таблице:

#### Работа с runtime окружением теста и доступ к зависимостям { #runtime-fs }
Метод | Описание
:--- | :---
`yatest.common.source_path` | Возвращает путь до файла от корня единого репозитория. Путь должен быть перечислен в макросе `DATA` в **ya.make**, начинаясь с `arcadia/`.
`yatest.common.test_source_path` | Возвращает путь до файла относительно расположения теста в репозитории.
`yatest.common.binary_path` | Возвращает путь до собранной программы, от которой зависит тест. Программа должна быть перечислена в секции `DEPENDS` в **ya.make** у теста. В качестве аргумента указывается путь, включающий имя файла программы.
`yatest.common.build_path` | Возвращает путь от корня сборочной директории для зависимостей теста.
`yatest.common.data_path` | Возвращает путь от корня каталога [arcadia_tests_data](https://a.yandex-team.ru/arc/trunk/arcadia_tests_data). Путь должен быть перечислен в макросе `DATA` в **ya.make** у теста и начинаться с `arcadia_tests_data/`.
`yatest.common.work_path` | Возвращает путь до рабочей директории теста, где можно сохранять временные данные.
`yatest.common.output_path` | Возвращает путь до директории `testing_out_stuff`. Данные сохранённые внутри неё будут доступны после тестирования.
`yatest.common.test_output_path` | Возвращает путь от директории `testing_out_stuff/<test_name>/path`. Директория `testing_out_stuff/<test_name>` будет создана автоматически.
`yatest.common.ram_drive_path` | Возвращает путь от RAM диска, если он предоставлен окружением. На Linux можно использовать опцию `--private-ram-drive` для предоставления индивидуального RAM диска для тестового узла, если он его заказывает с помощью `REQUIREMENTS(ram_disk:X)`, где X размер в GiB
`yatest.common.output_ram_drive_path` | Возвращает путь до уникальной созданной директории внутри RAM диска, контент которой будет перемещена в `testing_out_stuff/ram_drive_output` после тестирования.

#### Вспомогательные методы { #helpers }
Метод | Описание
:--- | :---
`yatest.common.execute` | Запускает внешнюю программу. В случае падения программы по сигналу, автоматически сохраняет core dump file, получает backtrace и привязывает эти данные к тесту.
`yatest.common.get_param` | Получить значение параметра, переданного через командную строку (`ya make -tt --test-param key=value`).
`yatest.common.network.get_port` | Получить указанный или произвольный свободный сетевой порт.
`yatest.common.python_path` | Возвращает путь до python binary.
`yatest.common.gdb_path` | Возвращает путь до gdb binary.
`yatest.common.java_bin` | Возвращает путь до java binary. В тесте требуется `DEPENDS(jdk)`.

#### Работа с каноническими данными { #canonization }
Подробней о канонизации читайте в [руководстве](./canon.md#python).

Метод | Описание
:--- | :---
`yatest.common.canonical_file` | Позволяет создать объект канонического файла, который можно вернуть из теста для его канонизации. Можно возвращать списки canonical_file, порядок имеет значение.
`yatest.common.canonical_dir` | Позволяет канонизировать директории целиком.
`yatest.common.canonical_execute` | Формирует канонический файл на основе stdout от запуска команды.
`yatest.common.canonical_py_execute` | Формирует канонический файл на основе stdout от запуска python-скрипта.

Пример получения доступа к данным из репозитория:

```python
import pytest
import yatest.common

def test_path():
    # Путь до файла из единого репозитория
    script_file = yatest.common.source_path('my-project/utils/script.sh')
    # Путь до каталога data рядом с тестом
    data_dir = yatest.common.test_source_path('data')
```

Получение доступа к тестовым параметрам:

```python
import pytest
import yatest.common

def test_parameters():
    # Получаем значение тестового параметра
    test_username = yatest.common.get_param('username')
```

Получение сетевого порта:

```python
import pytest
from yatest.common import network

def test_network_port():
    with network.PortManager() as pm:
        port = pm.get_port() # Свободный порт
```

Выполнение внешней программы:

```python
import pytest
import yatest.common

def test_execute():
    # Запускаем внешнюю команду
    p = yatest.common.execute(
        [ 'echo', 'hello, world!'],
        check_exit_code=False
    )
    code = p.exit_code
```

Канонизация файла в репозиторий с использованием внешнего diff_tool

```python
def test_canon():
    diff_tool = yatest.common.binary_path("path/to/diff_tool")
    with open("1.txt", "w") as afile:
        afile.write("canon data\n")
    return yatest.common.canonical_file("1.txt", diff_tool=[diff_tool, "--param1", "1", "--param2", "2"], local=True)
```

## Импорт-тесты { #import }

Для кода на Python при [ручном](../../usage/ya_make/tests.md#execution) и [автоматическом](https://docs.yandex-team.ru/devtools/test/automated) запуске тестов выполняется автоматическая проверка правильности импортов. Такая проверка позволяет быстро обнаруживать конфликты между библиотеками или отсутствие каких-то зависимостей в **ya.make** файлах. Проверка правильности импортов — ресурсоёмкая операция, и в настоящий момент выполняется только для исполняемых программ, т.е. модулей использующих один из следующих макросов:
* `PY2_PROGRAM`
* `PY3_PROGRAM`
* `PY2TEST`
* `PY3TEST`
* `PY23_TEST`

Проверяются только модули подключаемые к сборке через макрос `PY_SRCS`.  Проверку можно полностью отключить макросом `NO_CHECK_IMPORTS`:

```yamake
OWNER(g:my-group)

PY3TEST()

PY_SRCS(
    base.py
)

TEST_SRCS(
    test.py
)

SIZE(MEDIUM)

NO_CHECK_IMPORTS() # Отключить проверку импортируемости библиотек из PY_SRCS

NO_CHECK_IMPORTS( # Отключить проверку импортируемости только в указанных модулях
    devtools.pylibrary.*
)

END()
```

Бывает, что в библиотеках есть импорты, которые происходят по какому-то условию:

```python
if sys.platform.startswith("win32"):
    import psutil._psmswindows as _psplatform
```

Если импорт-тест падает в таком месте, можно отключить его следующим образом:

```yamake
NO_CHECK_IMPORTS( # Отключить проверку
    psutil._psmswindows
)
```

#### Pytest hooks { #pytesthooks }

С помощью механизма [pytest-хуков](https://docs.pytest.org/en/7.1.x/how-to/writing_hook_functions.html) предоставляется возможность кастомизации поведения аркадийного тест раннера.

Метод | Описание
:--- | :---
`pytest_ya_summarize_error(report)` | Позволяет кастомизировать экран с сообщением об ошибке теста 

##### Пример кастомизации экрана ошибки

В отчете можно использовать язык разметки, описанный по [ссылке](https://wiki.yandex-team.ru/yatool/dev/#markup). В `contest.py`-е своего проекта надо определить хук `pytest_ya_summarize_error()`:

```python
import io

from library.python.pytest.plugins import ya


def pytest_ya_summarize_error(report):
     """
     На вход приходит стандартный для pytest объект `report`
     """
     # Дефолтовое сообщение об ошибке
     rep = ya.get_formatted_error(report)

    output = io.StringIO()
    output.write(rep)
    output.write('\n\n[[rst]]\n')
    # Добавляем секции отчета
    for title, content in report.sections:
        output.write(f'[[rst]]>>> [[good]]{title}:[[rst]]\n')
        output.write(content)
    return output.getvalue()
```



## Статический анализ { #lint }

Все файлы на Python используемые, подключаемые в макросах `PY_SRCS` и `TEST_SRCS` в файлах **ya.make**, автоматически проверяются статическим анализатором [Flake8](https://gitlab.com/pycqa/flake8).

{% note info %}

Конфигурационный файл с настройками правил для Flake8 можно посмотреть [здесь](https://a.yandex-team.ru/arc/trunk/arcadia/build/config/tests/flake8/flake8.conf).

{% endnote %}

Для полного отключения таких проверок следует добавить в **ya.make** макрос `NO_LINT()` (допустимо только для директории `contrib`):

```yamake
OWNER(g:my-group)

PY3TEST()

TEST_SRCS(
    test.py
)

SIZE(MEDIUM)

NO_LINT() # Отключить статический анализ

END()

```

Также существует возможность отключить статический анализ отдельных строк в `*.py` файлах при помощи комментария `# noqa`:

```python
# Для этой строчки мы отключаем статический анализатор совсем
from sqlalchemy.orm import Query  # noqa

# Для этой строчки мы игнорируем ошибку E101 во Flake8
from region import Region  # noqa: E101
```

Расшифровку кодов ошибок можно посмотреть на следующих страницах:

* [https://www.flake8rules.com/](https://www.flake8rules.com/)
* [https://pypi.org/project/flake8-commas/](https://pypi.org/project/flake8-commas/)
* [http://www.pydocstyle.org/en/latest/error_codes.html](http://www.pydocstyle.org/en/latest/error_codes.html)
* [https://bandit.readthedocs.io/en/latest/plugins/index.html](https://bandit.readthedocs.io/en/latest/plugins/index.html)


### Плагины

[Список плагинов](https://a.yandex-team.ru/search?search=%2Ccontrib%252Fpython%252Fpytest-.*%252Fya%255C.make%2Cj%2Carcadia%2C%2C200), плагины  можно подключать просто по PEERDIR
 
Можно настраивать работу плагинов подавая аргумент `ya test --pytest-args "--all=x --pytest=y --args=z"`


### To be documented

```
PY2TEST/PY3TEST/PY23_TEST...
TEST_SRCS в PY2_LIBRARY
```

[https://wiki.yandex-team.ru/yatool/test/#python](https://wiki.yandex-team.ru/yatool/test/#python)

# Тесты на Java

Для Java [поддерживаются](https://docs.yandex-team.ru/devtools/test/intro#framework) [JUnit](https://junit.org/) версий 4.х и 5.х.

## Тесты на JUnit 4 { #junit4 }

Запуск тестов на JUnit 4 описывается макросом `JTEST()`:

```yamake
OWNER(g:my-group)

JTEST() # Используем JUnit 4

JAVA_SRCS(SRCDIR java **/*) # Где искать исходные коды тестов
JAVA_SRCS(SRCDIR resources **/*)

PEERDIR(
    # Сюда же необходимо добавить зависимости от исходных кодов вашего проекта
    contrib/java/junit/junit/4.12 # Сам фреймворк Junit 4
    contrib/java/org/hamcrest/hamcrest-all # Можно подключить набор Hamcrest матчеров
)

JVM_ARGS( # Необязательный набор флагов, передаваемых JVM
    -Djava.net.preferIPv6Addresses=true
    -Djava.security.egd=file:///dev/urandom
    -Xms128m
    -Xmx256m
)

SYSTEM_PROPERTIES( # Необязательный набор значений, которые нужно положить в Java system properties. Эти значения переопределяют те, что были переданы в JVM_ARGS при помощи -D.
    key1 val1
    key2 val2
    FILE app.properties # Положить содержимое *.properties или *.xml файла
    FILE config.xml
)


END()
```

{% note info %}

Примеры продвинутой работы с Java system properties можно посмотреть [здесь](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/dummy_arcadia/test_java_properties). Поддерживаются различные `${name}` подстановки и загрузка данных из XML файлов.

{% endnote %}


Код тестов совершенно стандартный, например:

```java
package ru.yandex.devtools.test;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public class MathsTest {

    @Test
    public void testMultiply() {
        assertEquals(2 * 2, 4);
    }

}
```

## Тесты на JUnit 5 { #junit5 }

Запуск тестов на JUnit 5 отличается только набором зависимостей и используемым макросом `JUNIT5`:

```yamake
OWNER(g:my-group)

JUNIT5() # Используем JUnit 5

JAVA_SRCS(SRCDIR java **/*)
JAVA_SRCS(SRCDIR resources **/*)

SIZE(MEDIUM)

INCLUDE(${ARCADIA_ROOT}/contrib/java/org/junit/junit-bom/5.7.1/ya.dependency_management.inc)
PEERDIR(
    # Сюда же необходимо добавить зависимости от исходных кодов вашего проекта
    contrib/java/org/junit/jupiter/junit-jupiter # Сам фреймворк Junit 5
    contrib/java/org/hamcrest/hamcrest-all # Набор Hamcrest матчеров
)

END()
```

Пример теста:

```java
package ru.yandex.devtools.test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import org.junit.jupiter.api.Test;

class MathsTest {

    @Test
    void multiplication() {
        assertEquals(2 * 2, 4);
    }

}
```

## Доступ к зависимостям { #dependencies }

Если вы используете в своем **ya.make** [зависимости](https://docs.yandex-team.ru/devtools/test/dependencies), то обращаться к таким данным в коде теста нужно, используя библиотеку [devtools/test/Paths](https://a.yandex-team.ru/arcadia/devtools/jtest/src/main/java/ru/yandex/devtools/test/Paths.java):

```java
package ru.yandex.devtools.test;

import org.junit.jupiter.api.Test;
import ru.yandex.devtools.test.Paths;

class ReadFileTest {

    @Test
    void read() {
        // Путь до файла/директории из репозитория, описанных с помощью макроса DATA("arcadia/devtools/dummy_arcadia/cat/main.cpp")
        String testFilePath = Paths.getSourcePath(
            "devtools/dummy_arcadia/cat/main.cpp"
        );

        // Путь до Sandbox-ресурса, описанного макросом DATA(sbr://53558626) # test.txt
        String sandboxResourcePath = Paths.getSandboxResourcesRoot() + "/test.txt";

        // Путь до файла из DEPENDS("devtools/dummy_arcadia/cat")
        // Обратите внимание: путь в DEPENDS указывает до сборочной цели, а BinaryPath требует указания пути до файла
        String binaryFilePath = Paths.getBuildPath(
            "devtools/dummy_arcadia/cat/cat"
        );

        // ...
    }

}
```

## Запуск JAVA_PROGRAM из теста

Если из теста есть необходимость запустить java-код, то можно воспользоваться следующим способом:
1. Добавить в `ya.make` теста конструкцию вида:
    ```
    PEERDIR(
        build/platform/java/jdk/jdk21
        ${JDK_RESOURCE_PEERDIR}
    )
    ```
2. Непосредственно в коде теста можно получить путь до JDK примерно так: 
    ```python
    import yatest.common.runtime as runtime

    class DummyTest:
        def __init__(self, ...):
            self.jdkPath = runtime.global_resources()['JDK21_RESOURCE_GLOBAL']
    ```
    Конечно, вместо JDK21 здесь и в предыдущем пункте можно подставить JDK нужной версии.
3. Полученный путь перед запуском jar-ника нужно выставить в переменную окружения `JAVA_HOME`:
    ```python 
    os.environ["JAVA_HOME"] = self.jdkPath
    ```

## Директории доступные тесту

Помимо доступа к зависимостям бибилотека devtools/test/Paths позволяет узнать правильные пути до:
 * `getWorkPath()` - Возвращает путь до рабочей директории теста, где можно сохранять временные данные.
 * `getTestOutputsRoot()` - Возвращает путь до директории `testing_out_stuff`. Данные сохранённые внутри неё будут доступны после тестирования.
 * `getRamDrivePath()` - путь к RAM drive заказаному тестом через [REQUIREMENTS](https://docs.yandex-team.ru/ya-make/manual/tests/common#requirements)
 * `getYtHddPath()` - путь к HDD диску доступному для записи временных данных для тестов запускаемых в [YT](https://docs.yandex-team.ru/devtools/test/yt)

## Фильтрация по тегам { #filtering }

Тесты JUnit5 можно фильтровать по тегам. Например: 

```java
package ru.yandex.devtools.test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import org.junit.jupiter.api.Test;

class MathsTest {

    @Test
    @Tag("mult")
    void multiplication() {
        assertEquals(2 * 2, 4);
    }

    @Test
    @Tag("sum")
    void sum() {
        assertEquals(2 + 2, 4);
    }

}
```

Запустить только тест `multiplcation` возможно с помощью 
```
ya make -t --junit-args '--junit-tags mult'
```

## Доступ к параметрам { #parameters }

Для того, чтобы получить в коде значения [параметров](https://docs.yandex-team.ru/devtools/test/manual#parameters):

```java
package ru.yandex.devtools.test;

import org.junit.jupiter.api.Test;
import ru.yandex.devtools.test.Params;

class ReadParametersTest {

    @Test
    void read() {
        // Значение параметра my-param
        String myParamValue = Params.params.get("my-param");

        // ...
    }

}
```

## Проверка classpath { #classpath-check }

Для тестов на Java возможно включить автоматическую проверку на наличие нескольких одинаковых классов в [Java Classpath](https://en.wikipedia.org/wiki/Classpath). В проверке участвует не только имя класса, но и хэш-сумма файла с его исходным кодом, так как идентичные классы из разных библиотек проблем вызывать не должны. Для включения этого типа тестов в ya.make файл соответствующего проекта нужно добавить макрос `CHECK_JAVA_DEPS(yes|no|strict)` [(docs)](/ya-make/manual/java/macros#check_java_deps):

```yamake
OWNER(g:my-group)

JTEST()

JAVA_SRCS(SRCDIR java **/*)
JAVA_SRCS(SRCDIR resources **/*)

CHECK_JAVA_DEPS(yes) # Включаем проверку classpath

END()

```

## Статический анализ { #lint }

На все исходные тексты на Java, которые подключены в секции `JAVA_SRCS` файла **ya.make**, включён статический анализ. Для проверки используется утилита [checkstyle](https://checkstyle.org/). Поддерживается два уровня проверок: **обычный** и **расширенный** (extended). В расширенном режиме выполняется большее количество проверок. Есть возможность полностью отключить статический анализ.

```yamake
OWNER(g:my-group)

JTEST()

JAVA_SRCS(SRCDIR java **/*)
JAVA_SRCS(SRCDIR resources **/*)

# Используйте один из следующих макросов:
LINT() # Включить статический анализатор
LINT(extended) # Включить статический анализатор в расширенном режиме (больше проверок)
NO_LINT() # Отключить статический анализатор

END()
```

{% note info %}

Конфигурационные файлы для статического анализа расположены [здесь](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/jstyle-runner/java/resources).

{% endnote %}

### To be documented

```
JTEST/JUNIT5
```

[https://wiki.yandex-team.ru/yatool/test/#java](https://wiki.yandex-team.ru/yatool/test/#java)
[https://wiki.yandex-team.ru/yatool/test/javacodestyle/](https://wiki.yandex-team.ru/yatool/test/javacodestyle/)


# Тесты на Go

{% note info %}

Пример проектов на Go можно найти [здесь](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/dummy_arcadia/go).

{% endnote %}

Тесты на [Go](https://golang.org/) пишутся и располагаются в дереве исходных кодов ровно также, как это делается во внешнем мире. Для файла с исходным кодом `file.go` его тесты по соглашению располагаются в том же каталоге в файле `file_test.go`. Разрешено использование Go [модулей](https://golang.org/ref/mod) и файлов `go.mod`. Подробности о том, как пишутся файлы с тестами, можно почитать в официальной [документации](https://golang.org/pkg/testing/). Распространенной практикой является использование в коде тестов инструментов из библиотеки [testify](https://github.com/stretchr/testify).

## Проект с тестами { #test }

Типичный проект с тестами на Go имеет такой **ya.make** файл в директории `my/package`:

```yamake
OWNER(g:some-group)

GO_LIBRARY() # Или GO_PROGRAM()

SRCS( # Исходные коды
    file.go
)

GO_TEST_SRCS( # Исходные коды internal тестов
    file_test.go
)

END()
```

В go поддерживается два вида тестов - внутрениие (internal) и внешние (external).

* **Внутренние тесты** принадлежат непосредственно тестируемому пакету. Для описания файлов с таким кодом используется макрос `GO_TEST_SRCS` как в примере выше.
* **Внешние тесты** собираются в отдельный пакет, который импортирует тестируемый. Обычно в коде таких тестов вызываются обычные публичные функции тестируемого пакета. Для описания кода таких тестов используется макрос `GO_XTEST_SRCS`.

Поскольку в системе сборки ya make тесты не могут быть в одном модуле с библиотекой для модуля тестов заводится отдельная вложенная директория (обычно называемая gotest). В ней размещается специальный модульный
макрос `GO_TEST_FOR(path/to/package)` ссылающийся на пакет с кодом тестов. В нём же описываются обычные [тестовые макросы](./common.md). Тестовый модуль собирается в специальный пакет, интегрированный, поддержанный
на уровне интеграции go-тестов и ya make. Этот пакет позволяет запускать как внутренние, так и внешние тесты со стандартными возможностями тестирования в Аркадии - [листингом](../../usage/ya_make/tests.md#test_list), [фильтрацией](../../usage/ya_make/tests.md#test_filtering), [канонизацией](./canon.md), [рецептами](./recipe.md) и [прочими](../../usage/ya_make/tests.md).

**Пример:** в директории `my/package/gotest будет` такой ya.make

```yamake
GO_TEST_FOR(my/package)

OWNER(g:some-group)

SIZE(MEDIUM)          # Тест среднего размера
REQUIREMENTS(ram:24)  # Требует для работы 24GiB памяти

END()
```

{% note alert %}

В go пакеты для тестирования собираются иначе, чем для обычной линковки. В частности тестовая сборка может экспортировать допольнительное "тестовое API" для *внешних* тестов. При этом go на линковке проверяет, что во всех частях сборки финального артефакта один и тото же пакет был одинаковым.
Эти два факта создают следующую проблему: при раздельной компиляции пакеты не знают для какого артефакта они собираются и потому всегда собираются с "обычными" версиями своих зависимостей.
Тесты собираются с тестовой версией тестируемого модуля. Если в рамках теста на тестируемый модуль есть транзитивная засисимость, то возникает проблема несовпадения хэшей (checksum mismatch) у тестируемого модуля.

Это поведение - проблема дизайна go (решение для go 2.0 обсуждается [здесь](https://github.com/golang/go/issues/29258)).

Cистема ya make не поддерживает это поведение и выдаёт ошибку конфигурирования *go test issue: transitive dependencies on modules under test are prohibited in Arcadia due to scalability issues*.

Сборка такого рода представляет существенную проблему поскольку ya make допускает одновременную сборку нескольких целей в одном сборочном графе (в пределе - вообще всех целей в автосборке).
В этом случае каждый модуль может иметь транзитивные зависимости на множество других модулей для которых в графе есть тесты и для каждой такой зависимости (да, и транзитивной тоже) придётся строить
свой вариант модуля. Сборка всего и всегда в тестовом вариенте неприемлема, поскольку предоставляет тестовое API вообще всем потребителям. В результате хорошего решения этой задачи не существет.
Есть дизайн с явной разметкой всех потенциально-проблемных зависимостей во всех модулях, но он сложный как в разработке, так и в использовании и поддержке.

**На данный момент тесты с такой проблемой собрать средствами ya make не представляется возможным. Решения этой проблемы, кроме отказа от использования "тестового API" не существует.**

{% endnote %}


Для того, чтобы поддерживать файлы **ya.make** в актуальном состоянии, существует специальный инструмент [yo](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/contrib/yo), автоматически обновляющий список файлов с исходными кодами и тестами в файле **ya.make**. После внесения изменений в проект достаточно выполнить одну команду, указав ей каталог с исходными кодами:

```bash
$ ya tool yo my-project/my-app/dir
```

Если `yo` у вас ещё не установлен, то он будет автоматически скачан при первом вызове команды.

## Доступ к зависимостям { #dependencies }

Если вы используете в своем **ya.make** [зависимости](https://docs.yandex-team.ru/devtools/test/dependencies), то обращаться к таким данным в коде теста нужно, используя библиотеку [yatest](https://a.yandex-team.ru/arcadia/library/go/test/yatest/env.go):

```go
import (
    "a.yandex-team.ru/library/go/test/yatest"
)

func TestDependencies(t *testing.T) {
    // Путь до файла/директории из репозитория, описанных с помощью макроса DATA("arcadia/devtools/dummy_arcadia/cat/main.cpp")
    filePath := yatest.SourcePath("devtools/dummy_arcadia/cat/main.cpp");

    // Путь до Sandbox-ресурса, описанного макросом DATA(sbr://53558626) # test.txt
    dataFile := yatest.WorkPath("test.txt");

    // Путь до файла из DEPENDS("devtools/dummy_arcadia/cat/cat")
    // Обратите внимание: путь в DEPENDS указывает до сборочной цели, а BinaryPath требует указания пути до файла
    binary, err := yatest.BinaryPath("devtools/dummy_arcadia/cat/cat")
	require.NoError(t, err)
}
```

## Проект с бенчмарками { #benchmark }

Кроме обычных тестов существует возможность запускать [бенчмарки](https://golang.org/pkg/testing/#hdr-Benchmarks):

```yamake
OWNER(g:some-group)

GO_TEST()

GO_TEST_SRCS(
    benchmark_test.go
)

TAG(ya:run_go_benchmark ya:manual)

END()
```

Код бенчмарков [пишется](https://a.yandex-team.ru/arc/trunk/arcadia/devtools/dummy_arcadia/go/go_benchmarks/) так, как показано в официальной документации Golang.


### To be documented

```
GO_TEST/GO_TEST_FOR
```
