// Every operator new returns zeroed memory. Some game and Kinoko state
// (Kinoko's Vector3f, members without initializers) relied on the 3DS handing
// out memory that happened to be zero; on the Vita, reused heap memory holds
// old values (a NaN camera position hid every race model). Pairs with
// -ftrivial-auto-var-init=zero for automatics (CMakeLists.txt).
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <malloc.h>
#include <new>

namespace {
void* zeroed(std::size_t size, std::size_t alignment) {
	if (!size) size = 1;
	void* p = alignment > alignof(std::max_align_t) ? memalign(alignment, size) : std::malloc(size);
	if (p) std::memset(p, 0, size);
	return p;
}
}

void* operator new(std::size_t size) { return zeroed(size, 0); }
void* operator new[](std::size_t size) { return zeroed(size, 0); }
void* operator new(std::size_t size, const std::nothrow_t&) noexcept { return zeroed(size, 0); }
void* operator new[](std::size_t size, const std::nothrow_t&) noexcept { return zeroed(size, 0); }
void* operator new(std::size_t size, std::align_val_t a) { return zeroed(size, std::size_t(a)); }
void* operator new[](std::size_t size, std::align_val_t a) { return zeroed(size, std::size_t(a)); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
void operator delete(void* p, std::align_val_t) noexcept { std::free(p); }
void operator delete[](void* p, std::align_val_t) noexcept { std::free(p); }
void operator delete(void* p, std::size_t, std::align_val_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t, std::align_val_t) noexcept { std::free(p); }
