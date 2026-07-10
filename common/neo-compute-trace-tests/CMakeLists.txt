cmake_minimum_required(VERSION 3.16)
project(neo_compute_trace_tests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(neo-trace-test trace-test.cpp)
target_compile_definitions(neo-trace-test PRIVATE NEO_COMPUTE_TRACE NEO_COMPUTE_TRACE_TESTING)
target_include_directories(neo-trace-test PRIVATE ../../ggml/include)

add_executable(neo-trace-disabled-test trace-disabled-test.cpp)
target_include_directories(neo-trace-disabled-test PRIVATE ../../ggml/include)
