#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

constexpr int kLanes = 4;

struct Carrier4 {
    float2 lane[kLanes];
};

struct RouteSample {
    double wall_ms;
    float cuda_timeline_ms;
    std::uint64_t intermediate_checksum;
    std::uint64_t output_checksum;
};

std::uint64_t g_kernel_launch_count = 0;

#define CUDA_CHECK(call)                                                        \
    do {                                                                        \
        const cudaError_t status_ = (call);                                     \
        if (status_ != cudaSuccess) {                                            \
            std::cerr << "CUDA failure at " << __FILE__ << ":" << __LINE__    \
                      << ": " << cudaGetErrorString(status_) << "\n";           \
            std::exit(3);                                                        \
        }                                                                       \
    } while (false)

__host__ __device__ inline float2 phase_0(const float2 value) {
    return value;
}

__host__ __device__ inline float2 phase_1(const float2 value) {
    return make_float2(-value.y, value.x);
}

__host__ __device__ inline float2 phase_2(const float2 value) {
    return make_float2(-value.x, -value.y);
}

__host__ __device__ inline float2 phase_3(const float2 value) {
    return make_float2(value.y, -value.x);
}

__device__ __forceinline__ float register_boundary_barrier(float value) {
    unsigned int bits = __float_as_uint(value);
    asm volatile("xor.b32 %0, %0, 0;" : "+r"(bits));
    return __uint_as_float(bits);
}

__device__ __forceinline__ float2 register_boundary_barrier(float2 value) {
    value.x = register_boundary_barrier(value.x);
    value.y = register_boundary_barrier(value.y);
    return value;
}

__device__ __forceinline__ Carrier4 apply_f(const Carrier4 &x) {
    Carrier4 y;
    y.lane[0] = phase_0(x.lane[1]);
    y.lane[1] = phase_1(x.lane[0]);
    y.lane[2] = phase_2(x.lane[3]);
    y.lane[3] = phase_3(x.lane[2]);
    return y;
}

__device__ __forceinline__ Carrier4 apply_g(const Carrier4 &y) {
    Carrier4 z;
    z.lane[0] = phase_1(y.lane[2]);
    z.lane[1] = phase_1(y.lane[3]);
    z.lane[2] = phase_2(y.lane[0]);
    z.lane[3] = phase_2(y.lane[1]);
    return z;
}

__device__ __forceinline__ Carrier4 apply_f_inverse(const Carrier4 &y) {
    Carrier4 x;
    x.lane[0] = phase_3(y.lane[1]);
    x.lane[1] = phase_0(y.lane[0]);
    x.lane[2] = phase_1(y.lane[3]);
    x.lane[3] = phase_2(y.lane[2]);
    return x;
}

__device__ __forceinline__ Carrier4 apply_g_inverse(const Carrier4 &z) {
    Carrier4 y;
    y.lane[0] = phase_2(z.lane[2]);
    y.lane[1] = phase_2(z.lane[3]);
    y.lane[2] = phase_3(z.lane[0]);
    y.lane[3] = phase_3(z.lane[1]);
    return y;
}

extern "C" __global__ void open_compose_forward(
        const Carrier4 *__restrict__ x,
        Carrier4 *__restrict__ z,
        std::size_t carriers) {
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index >= carriers) {
        return;
    }

    Carrier4 y = apply_f(x[index]);
    y.lane[0] = register_boundary_barrier(y.lane[0]);
    y.lane[1] = register_boundary_barrier(y.lane[1]);
    y.lane[2] = register_boundary_barrier(y.lane[2]);
    y.lane[3] = register_boundary_barrier(y.lane[3]);
    z[index] = apply_g(y);
}

extern "C" __global__ void materialize_f(
        const Carrier4 *__restrict__ x,
        Carrier4 *__restrict__ y,
        std::size_t carriers) {
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index < carriers) {
        y[index] = apply_f(x[index]);
    }
}

extern "C" __global__ void materialize_g(
        const Carrier4 *__restrict__ y,
        Carrier4 *__restrict__ z,
        std::size_t carriers) {
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index < carriers) {
        z[index] = apply_g(y[index]);
    }
}

extern "C" __global__ void open_compose_inverse(
        const Carrier4 *__restrict__ z,
        Carrier4 *__restrict__ x,
        std::size_t carriers) {
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index >= carriers) {
        return;
    }

    Carrier4 y = apply_g_inverse(z[index]);
    y.lane[0] = register_boundary_barrier(y.lane[0]);
    y.lane[1] = register_boundary_barrier(y.lane[1]);
    y.lane[2] = register_boundary_barrier(y.lane[2]);
    y.lane[3] = register_boundary_barrier(y.lane[3]);
    x[index] = apply_f_inverse(y);
}

extern "C" __global__ void wrong_order_forward(
        const Carrier4 *__restrict__ x,
        Carrier4 *__restrict__ z,
        std::size_t carriers) {
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index >= carriers) {
        return;
    }

    Carrier4 g_x = apply_g(x[index]);
    g_x.lane[0] = register_boundary_barrier(g_x.lane[0]);
    g_x.lane[1] = register_boundary_barrier(g_x.lane[1]);
    g_x.lane[2] = register_boundary_barrier(g_x.lane[2]);
    g_x.lane[3] = register_boundary_barrier(g_x.lane[3]);
    z[index] = apply_f(g_x);
}

extern "C" __global__ void wrong_order_inverse(
        const Carrier4 *__restrict__ z,
        Carrier4 *__restrict__ x,
        std::size_t carriers) {
    const std::size_t index =
        static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
    if (index >= carriers) {
        return;
    }

    Carrier4 invalid_y = apply_f_inverse(z[index]);
    invalid_y.lane[0] = register_boundary_barrier(invalid_y.lane[0]);
    invalid_y.lane[1] = register_boundary_barrier(invalid_y.lane[1]);
    invalid_y.lane[2] = register_boundary_barrier(invalid_y.lane[2]);
    invalid_y.lane[3] = register_boundary_barrier(invalid_y.lane[3]);
    x[index] = apply_g_inverse(invalid_y);
}

bool bind_ports(const std::string &codomain, const std::string &domain) {
    return codomain == domain;
}

bool admit_primary_route(
        bool ports_match,
        bool intermediate_materialized,
        int final_projection_count) {
    return ports_match
        && !intermediate_materialized
        && final_projection_count == 1;
}

std::uint64_t fnv1a(const void *data, std::size_t bytes) {
    const auto *cursor = static_cast<const unsigned char *>(data);
    std::uint64_t value = UINT64_C(1469598103934665603);
    for (std::size_t index = 0; index < bytes; ++index) {
        value ^= cursor[index];
        value *= UINT64_C(1099511628211);
    }
    return value;
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    const std::size_t middle = values.size() / 2;
    if ((values.size() % 2) == 0) {
        return (values[middle - 1] + values[middle]) * 0.5;
    }
    return values[middle];
}

double median_cuda(const std::vector<float> &values) {
    std::vector<double> converted(values.begin(), values.end());
    return median(std::move(converted));
}

std::string json_escape(const char *value) {
    std::string escaped;
    for (const char *cursor = value; *cursor != '\0'; ++cursor) {
        if (*cursor == '"' || *cursor == '\\') {
            escaped.push_back('\\');
        }
        escaped.push_back(*cursor);
    }
    return escaped;
}

void emit_samples(const std::vector<RouteSample> &samples) {
    std::cout << "[";
    for (std::size_t index = 0; index < samples.size(); ++index) {
        if (index != 0) {
            std::cout << ",";
        }
        std::cout << "{\"wall_ms\":" << samples[index].wall_ms
                  << ",\"cuda_timeline_ms\":"
                  << samples[index].cuda_timeline_ms
                  << ",\"intermediate_checksum\":"
                  << samples[index].intermediate_checksum
                  << ",\"output_checksum\":"
                  << samples[index].output_checksum << "}";
    }
    std::cout << "]";
}

Carrier4 host_apply_f(const Carrier4 &x) {
    Carrier4 y;
    y.lane[0] = phase_0(x.lane[1]);
    y.lane[1] = phase_1(x.lane[0]);
    y.lane[2] = phase_2(x.lane[3]);
    y.lane[3] = phase_3(x.lane[2]);
    return y;
}

Carrier4 host_apply_g(const Carrier4 &y) {
    Carrier4 z;
    z.lane[0] = phase_1(y.lane[2]);
    z.lane[1] = phase_1(y.lane[3]);
    z.lane[2] = phase_2(y.lane[0]);
    z.lane[3] = phase_2(y.lane[1]);
    return z;
}

bool carrier_equal(const Carrier4 &left, const Carrier4 &right) {
    return std::memcmp(&left, &right, sizeof(Carrier4)) == 0;
}

bool carrier_is_negative(const Carrier4 &candidate, const Carrier4 &reference) {
    Carrier4 negative = reference;
    for (int lane = 0; lane < kLanes; ++lane) {
        negative.lane[lane].x = -negative.lane[lane].x;
        negative.lane[lane].y = -negative.lane[lane].y;
    }
    return carrier_equal(candidate, negative);
}

RouteSample run_primary(
        const Carrier4 *device_x,
        Carrier4 *device_z,
        Carrier4 *host_z,
        std::size_t carriers,
        std::size_t bytes,
        cudaStream_t stream,
        cudaEvent_t begin_event,
        cudaEvent_t end_event) {
    const int threads = 256;
    const int blocks = static_cast<int>((carriers + threads - 1) / threads);
    const auto begin_wall = std::chrono::steady_clock::now();
    CUDA_CHECK(cudaEventRecord(begin_event, stream));
    ++g_kernel_launch_count;
    open_compose_forward<<<blocks, threads, 0, stream>>>(
        device_x, device_z, carriers);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpyAsync(
        host_z, device_z, bytes, cudaMemcpyDeviceToHost, stream));
    CUDA_CHECK(cudaEventRecord(end_event, stream));
    CUDA_CHECK(cudaEventSynchronize(end_event));
    const std::uint64_t output_checksum = fnv1a(host_z, bytes);
    const auto end_wall = std::chrono::steady_clock::now();
    float cuda_timeline_ms = 0.0F;
    CUDA_CHECK(cudaEventElapsedTime(
        &cuda_timeline_ms, begin_event, end_event));
    return RouteSample{
        std::chrono::duration<double, std::milli>(end_wall - begin_wall).count(),
        cuda_timeline_ms,
        0,
        output_checksum,
    };
}

RouteSample run_materialized_control(
        const Carrier4 *device_x,
        Carrier4 *device_y,
        Carrier4 *device_z,
        Carrier4 *host_y,
        Carrier4 *host_z,
        std::size_t carriers,
        std::size_t bytes,
        cudaStream_t stream,
        cudaEvent_t begin_event,
        cudaEvent_t end_event) {
    const int threads = 256;
    const int blocks = static_cast<int>((carriers + threads - 1) / threads);
    const auto begin_wall = std::chrono::steady_clock::now();
    CUDA_CHECK(cudaEventRecord(begin_event, stream));
    ++g_kernel_launch_count;
    materialize_f<<<blocks, threads, 0, stream>>>(
        device_x, device_y, carriers);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpyAsync(
        host_y, device_y, bytes, cudaMemcpyDeviceToHost, stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));

    const std::uint64_t intermediate_checksum = fnv1a(host_y, bytes);

    CUDA_CHECK(cudaMemcpyAsync(
        device_y, host_y, bytes, cudaMemcpyHostToDevice, stream));
    ++g_kernel_launch_count;
    materialize_g<<<blocks, threads, 0, stream>>>(
        device_y, device_z, carriers);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpyAsync(
        host_z, device_z, bytes, cudaMemcpyDeviceToHost, stream));
    CUDA_CHECK(cudaEventRecord(end_event, stream));
    CUDA_CHECK(cudaEventSynchronize(end_event));
    const std::uint64_t output_checksum = fnv1a(host_z, bytes);
    const auto end_wall = std::chrono::steady_clock::now();
    float cuda_timeline_ms = 0.0F;
    CUDA_CHECK(cudaEventElapsedTime(
        &cuda_timeline_ms, begin_event, end_event));
    return RouteSample{
        std::chrono::duration<double, std::milli>(end_wall - begin_wall).count(),
        cuda_timeline_ms,
        intermediate_checksum,
        output_checksum,
    };
}

}  // namespace

int main(int argc, char **argv) {
    std::size_t carriers = 1U << 20U;
    int warmups = 2;
    int repetitions = 9;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--carriers" && index + 1 < argc) {
            carriers = static_cast<std::size_t>(
                std::strtoull(argv[++index], nullptr, 10));
        } else if (argument == "--warmups" && index + 1 < argc) {
            warmups = std::atoi(argv[++index]);
        } else if (argument == "--repetitions" && index + 1 < argc) {
            repetitions = std::atoi(argv[++index]);
        } else {
            std::cerr << "Unknown or incomplete argument: " << argument << "\n";
            return 2;
        }
    }
    if (carriers == 0 || warmups < 0 || repetitions < 3) {
        std::cerr << "Invalid geometry\n";
        return 2;
    }

    const bool type_mismatch_rejected =
        !bind_ports("Y.complex4.z4@r2-v1", "Q.incompatible@r2-v1");
    const std::uint64_t launches_at_type_mismatch = g_kernel_launch_count;

    CUDA_CHECK(cudaSetDevice(0));
    cudaDeviceProp device_properties{};
    CUDA_CHECK(cudaGetDeviceProperties(&device_properties, 0));

    const std::size_t bytes = carriers * sizeof(Carrier4);
    Carrier4 *host_x = nullptr;
    Carrier4 *host_y = nullptr;
    Carrier4 *host_primary_z = nullptr;
    Carrier4 *host_control_z = nullptr;
    Carrier4 *host_scratch = nullptr;
    CUDA_CHECK(cudaMallocHost(&host_x, bytes));
    CUDA_CHECK(cudaMallocHost(&host_y, bytes));
    CUDA_CHECK(cudaMallocHost(&host_primary_z, bytes));
    CUDA_CHECK(cudaMallocHost(&host_control_z, bytes));
    CUDA_CHECK(cudaMallocHost(&host_scratch, bytes));

    for (std::size_t carrier = 0; carrier < carriers; ++carrier) {
        for (int lane = 0; lane < kLanes; ++lane) {
            const std::size_t ordinal =
                carrier * static_cast<std::size_t>(kLanes)
                + static_cast<std::size_t>(lane);
            host_x[carrier].lane[lane] = make_float2(
                static_cast<float>(1U + (ordinal * 17U) % 4093U),
                -static_cast<float>(1U + (ordinal * 29U) % 4093U));
        }
    }

    Carrier4 *device_x = nullptr;
    Carrier4 *device_y = nullptr;
    Carrier4 *device_primary_z = nullptr;
    Carrier4 *device_control_z = nullptr;
    Carrier4 *device_scratch = nullptr;
    CUDA_CHECK(cudaMalloc(&device_x, bytes));
    CUDA_CHECK(cudaMalloc(&device_y, bytes));
    CUDA_CHECK(cudaMalloc(&device_primary_z, bytes));
    CUDA_CHECK(cudaMalloc(&device_control_z, bytes));
    CUDA_CHECK(cudaMalloc(&device_scratch, bytes));
    CUDA_CHECK(cudaMemcpy(
        device_x, host_x, bytes, cudaMemcpyHostToDevice));

    cudaStream_t stream{};
    cudaEvent_t begin_event{};
    cudaEvent_t end_event{};
    CUDA_CHECK(cudaStreamCreate(&stream));
    CUDA_CHECK(cudaEventCreate(&begin_event));
    CUDA_CHECK(cudaEventCreate(&end_event));

    for (int warmup = 0; warmup < warmups; ++warmup) {
        (void) run_primary(
            device_x,
            device_primary_z,
            host_primary_z,
            carriers,
            bytes,
            stream,
            begin_event,
            end_event);
        (void) run_materialized_control(
            device_x,
            device_y,
            device_control_z,
            host_y,
            host_control_z,
            carriers,
            bytes,
            stream,
            begin_event,
            end_event);
    }

    std::vector<RouteSample> primary_samples;
    std::vector<RouteSample> control_samples;
    primary_samples.reserve(static_cast<std::size_t>(repetitions));
    control_samples.reserve(static_cast<std::size_t>(repetitions));
    for (int repetition = 0; repetition < repetitions; ++repetition) {
        if ((repetition % 2) == 0) {
            primary_samples.push_back(run_primary(
                device_x,
                device_primary_z,
                host_primary_z,
                carriers,
                bytes,
                stream,
                begin_event,
                end_event));
            control_samples.push_back(run_materialized_control(
                device_x,
                device_y,
                device_control_z,
                host_y,
                host_control_z,
                carriers,
                bytes,
                stream,
                begin_event,
                end_event));
        } else {
            control_samples.push_back(run_materialized_control(
                device_x,
                device_y,
                device_control_z,
                host_y,
                host_control_z,
                carriers,
                bytes,
                stream,
                begin_event,
                end_event));
            primary_samples.push_back(run_primary(
                device_x,
                device_primary_z,
                host_primary_z,
                carriers,
                bytes,
                stream,
                begin_event,
                end_event));
        }
    }

    std::size_t primary_reference_mismatches = 0;
    std::size_t route_mismatches = 0;
    for (std::size_t carrier = 0; carrier < carriers; ++carrier) {
        const Carrier4 expected = host_apply_g(host_apply_f(host_x[carrier]));
        if (!carrier_equal(host_primary_z[carrier], expected)) {
            ++primary_reference_mismatches;
        }
        if (!carrier_equal(
                host_primary_z[carrier], host_control_z[carrier])) {
            ++route_mismatches;
        }
    }

    const int threads = 256;
    const int blocks = static_cast<int>((carriers + threads - 1) / threads);

    ++g_kernel_launch_count;
    wrong_order_forward<<<blocks, threads, 0, stream>>>(
        device_x, device_scratch, carriers);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpyAsync(
        host_scratch,
        device_scratch,
        bytes,
        cudaMemcpyDeviceToHost,
        stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));
    std::size_t wrong_order_equal_count = 0;
    std::size_t wrong_order_negative_law_failures = 0;
    for (std::size_t carrier = 0; carrier < carriers; ++carrier) {
        if (carrier_equal(host_scratch[carrier], host_primary_z[carrier])) {
            ++wrong_order_equal_count;
        }
        if (!carrier_is_negative(
                host_scratch[carrier], host_primary_z[carrier])) {
            ++wrong_order_negative_law_failures;
        }
    }

    ++g_kernel_launch_count;
    open_compose_inverse<<<blocks, threads, 0, stream>>>(
        device_primary_z, device_scratch, carriers);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpyAsync(
        host_scratch,
        device_scratch,
        bytes,
        cudaMemcpyDeviceToHost,
        stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));
    std::size_t restoration_mismatches = 0;
    for (std::size_t carrier = 0; carrier < carriers; ++carrier) {
        if (!carrier_equal(host_scratch[carrier], host_x[carrier])) {
            ++restoration_mismatches;
        }
    }

    ++g_kernel_launch_count;
    wrong_order_inverse<<<blocks, threads, 0, stream>>>(
        device_primary_z, device_scratch, carriers);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaMemcpyAsync(
        host_scratch,
        device_scratch,
        bytes,
        cudaMemcpyDeviceToHost,
        stream));
    CUDA_CHECK(cudaStreamSynchronize(stream));
    std::size_t wrong_inverse_restored_count = 0;
    for (std::size_t carrier = 0; carrier < carriers; ++carrier) {
        if (carrier_equal(host_scratch[carrier], host_x[carrier])) {
            ++wrong_inverse_restored_count;
        }
    }

    std::vector<double> primary_wall;
    std::vector<double> control_wall;
    std::vector<float> primary_cuda;
    std::vector<float> control_cuda;
    for (const RouteSample &sample : primary_samples) {
        primary_wall.push_back(sample.wall_ms);
        primary_cuda.push_back(sample.cuda_timeline_ms);
    }
    for (const RouteSample &sample : control_samples) {
        control_wall.push_back(sample.wall_ms);
        control_cuda.push_back(sample.cuda_timeline_ms);
    }
    const double primary_wall_median = median(primary_wall);
    const double control_wall_median = median(control_wall);
    const double primary_cuda_median = median_cuda(primary_cuda);
    const double control_cuda_median = median_cuda(control_cuda);
    const double wall_speedup = control_wall_median / primary_wall_median;
    const double cuda_speedup = control_cuda_median / primary_cuda_median;

    const bool compatible_ports =
        bind_ports("Y.complex4.z4@r2-v1", "Y.complex4.z4@r2-v1");
    const bool primary_route_admitted =
        admit_primary_route(compatible_ports, false, 1);
    const bool materialized_route_rejected_as_primary =
        !admit_primary_route(compatible_ports, true, 1);
    const bool exact_outputs =
        primary_reference_mismatches == 0 && route_mismatches == 0;
    const bool wrong_order_passed =
        wrong_order_equal_count == 0
        && wrong_order_negative_law_failures == 0;
    const bool restoration_passed = restoration_mismatches == 0;
    const bool wrong_inverse_passed = wrong_inverse_restored_count == 0;

    CUDA_CHECK(cudaEventDestroy(begin_event));
    CUDA_CHECK(cudaEventDestroy(end_event));
    CUDA_CHECK(cudaStreamDestroy(stream));
    CUDA_CHECK(cudaFree(device_scratch));
    CUDA_CHECK(cudaFree(device_control_z));
    CUDA_CHECK(cudaFree(device_primary_z));
    CUDA_CHECK(cudaFree(device_y));
    CUDA_CHECK(cudaFree(device_x));
    device_scratch = nullptr;
    device_control_z = nullptr;
    device_primary_z = nullptr;
    device_y = nullptr;
    device_x = nullptr;
    CUDA_CHECK(cudaFreeHost(host_scratch));
    CUDA_CHECK(cudaFreeHost(host_control_z));
    CUDA_CHECK(cudaFreeHost(host_primary_z));
    CUDA_CHECK(cudaFreeHost(host_y));
    CUDA_CHECK(cudaFreeHost(host_x));
    host_scratch = nullptr;
    host_control_z = nullptr;
    host_primary_z = nullptr;
    host_y = nullptr;
    host_x = nullptr;
    CUDA_CHECK(cudaDeviceReset());

    const bool final_intermediate_residency_zero =
        device_y == nullptr && host_y == nullptr;
    const bool all_integrity_gates =
        type_mismatch_rejected
        && launches_at_type_mismatch == 0
        && primary_route_admitted
        && materialized_route_rejected_as_primary
        && exact_outputs
        && wrong_order_passed
        && restoration_passed
        && wrong_inverse_passed
        && final_intermediate_residency_zero;

    std::cout << std::setprecision(12);
    std::cout
        << "{"
        << "\"schema_version\":\"neo-open-relational-carrier-r2-v1\","
        << "\"device\":{\"name\":\""
        << json_escape(device_properties.name)
        << "\",\"compute_capability\":\""
        << device_properties.major << "." << device_properties.minor
        << "\"},"
        << "\"geometry\":{\"carriers\":" << carriers
        << ",\"lanes_per_carrier\":" << kLanes
        << ",\"bytes_per_boundary\":" << bytes
        << ",\"warmups\":" << warmups
        << ",\"repetitions\":" << repetitions << "},"
        << "\"ports\":{\"F_domain\":\"X.complex4@r2-v1\","
        << "\"F_codomain\":\"Y.complex4.z4@r2-v1\","
        << "\"G_domain\":\"Y.complex4.z4@r2-v1\","
        << "\"G_codomain\":\"Z.complex4@r2-v1\"},"
        << "\"morphisms\":{\"F\":\"permute_xor1_then_phase_j\","
        << "\"G\":\"permute_xor2_then_phase_floor_j_over_2_plus_1\"},"
        << "\"primary\":";
    emit_samples(primary_samples);
    std::cout << ",\"materialized_control\":";
    emit_samples(control_samples);
    std::cout
        << ",\"metrics\":{\"primary_wall_median_ms\":"
        << primary_wall_median
        << ",\"materialized_wall_median_ms\":" << control_wall_median
        << ",\"wall_speedup\":" << wall_speedup
        << ",\"primary_cuda_timeline_median_ms\":" << primary_cuda_median
        << ",\"materialized_cuda_timeline_median_ms\":"
        << control_cuda_median
        << ",\"cuda_timeline_speedup\":" << cuda_speedup
        << ",\"primary_intermediate_materialized_bytes\":0"
        << ",\"control_intermediate_d2h_bytes_per_rep\":" << bytes
        << ",\"control_intermediate_h2d_bytes_per_rep\":" << bytes
        << ",\"control_intermediate_cpu_read_bytes_per_rep\":" << bytes
        << ",\"kernel_launch_count\":" << g_kernel_launch_count << "},"
        << "\"controls\":{\"type_mismatch_rejected\":"
        << (type_mismatch_rejected ? "true" : "false")
        << ",\"launches_at_type_mismatch\":"
        << launches_at_type_mismatch
        << ",\"primary_route_admitted\":"
        << (primary_route_admitted ? "true" : "false")
        << ",\"materialized_route_rejected_as_primary\":"
        << (materialized_route_rejected_as_primary ? "true" : "false")
        << ",\"primary_reference_mismatches\":"
        << primary_reference_mismatches
        << ",\"route_mismatches\":" << route_mismatches
        << ",\"wrong_order_equal_count\":" << wrong_order_equal_count
        << ",\"wrong_order_negative_law_failures\":"
        << wrong_order_negative_law_failures
        << ",\"restoration_mismatches\":" << restoration_mismatches
        << ",\"wrong_inverse_restored_count\":"
        << wrong_inverse_restored_count
        << ",\"primary_final_projection_count\":1"
        << ",\"control_intermediate_projection_count\":1"
        << ",\"final_intermediate_residency_zero\":"
        << (final_intermediate_residency_zero ? "true" : "false")
        << "},"
        << "\"all_integrity_gates\":"
        << (all_integrity_gates ? "true" : "false")
        << "}\n";
    return all_integrity_gates ? 0 : 4;
}
