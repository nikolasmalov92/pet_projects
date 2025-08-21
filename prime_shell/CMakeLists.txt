cmake_minimum_required(VERSION 3.28)
project(prime_shell)

set(CMAKE_CXX_STANDARD 20)

# для статической линковки
set(CMAKE_EXE_LINKER_FLAGS "-static -static-libgcc -static-libstdc++")
set(CMAKE_SHARED_LINKER_FLAGS "-static -static-libgcc -static-libstdc++")
set(CMAKE_MODULE_LINKER_FLAGS "-static -static-libgcc -static-libstdc++")

add_executable(prime_shell main.cpp
)
