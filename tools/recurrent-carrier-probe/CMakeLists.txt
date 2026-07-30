set(TARGET llama-recurrent-carrier-probe)
add_executable(
    ${TARGET}
    recurrent-carrier-probe.cpp
    recurrent-carrier-evidence.cpp)
target_include_directories(${TARGET} PRIVATE ${CMAKE_SOURCE_DIR}/src)
target_link_libraries(${TARGET} PRIVATE llama-common llama ${CMAKE_THREAD_LIBS_INIT})
target_compile_features(${TARGET} PRIVATE cxx_std_17)

set(SELFTEST_TARGET llama-recurrent-carrier-probe-selftest)
add_executable(
    ${SELFTEST_TARGET}
    recurrent-carrier-probe-selftest.cpp
    recurrent-carrier-evidence.cpp)
target_include_directories(
    ${SELFTEST_TARGET}
    PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/ggml/src)
target_link_libraries(
    ${SELFTEST_TARGET}
    PRIVATE
    llama-common
    llama
    ${CMAKE_THREAD_LIBS_INIT})
target_compile_features(${SELFTEST_TARGET} PRIVATE cxx_std_17)

if(LLAMA_TOOLS_INSTALL)
    install(TARGETS ${TARGET} RUNTIME)
endif()
