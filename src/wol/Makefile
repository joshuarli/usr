wol:
	clang -O3 -march=native -pipe -flto \
	-Wall -Wextra -Wpedantic \
	-Wl,-dead_strip \
	-Wl,-dead_strip_dylibs \
	-Wl,-x \
	-o wol wol.c
