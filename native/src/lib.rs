//! Allocation-free frame observations. No OCR decisions, model calls or I/O.
#![deny(unsafe_op_in_unsafe_fn)]

pub const ABI_VERSION: u32 = 1;
pub const MAX_BYTES: usize = 16 * 1024 * 1024;

#[derive(Debug, PartialEq, Eq)]
pub struct Metrics {
    pub changed_pixels: u64,
    pub absolute_delta: u64,
}

#[derive(Debug, PartialEq, Eq)]
pub enum FrameError {
    InvalidShape,
    InvalidLength,
}

/// Compare contiguous u8 pixels with `channels` values per pixel.
/// Integer totals preserve the Python oracle's uint8 result exactly.
pub fn frame_metrics_u8(left: &[u8], right: &[u8], channels: usize) -> Result<Metrics, FrameError> {
    if channels == 0 || left.is_empty() || !left.len().is_multiple_of(channels) {
        return Err(FrameError::InvalidShape);
    }
    if left.len() != right.len() || left.len() > MAX_BYTES {
        return Err(FrameError::InvalidLength);
    }
    let mut result = Metrics {
        changed_pixels: 0,
        absolute_delta: 0,
    };
    for (a, b) in left.chunks_exact(channels).zip(right.chunks_exact(channels)) {
        let mut changed = false;
        for (&x, &y) in a.iter().zip(b) {
            changed |= x != y;
            result.absolute_delta += u64::from(x.abs_diff(y));
        }
        result.changed_pixels += u64::from(changed);
    }
    Ok(result)
}

#[unsafe(no_mangle)]
pub extern "C" fn cloudhime_abi_version() -> u32 {
    ABI_VERSION
}

/// C ABI: 0=success, 1=invalid argument, 2=unexpected panic.
/// Output values are left untouched on failure.
///
/// # Safety
/// Each input pointer must reference `pixels * channels` initialized bytes in
/// one allocation, readable and immutable throughout this call. Each output
/// pointer must reference an aligned, writable u64. Output buffers must not
/// overlap each other or the inputs. The caller retains ownership of all buffers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cloudhime_frame_metrics_u8(
    left: *const u8,
    right: *const u8,
    pixels: usize,
    channels: usize,
    changed_pixels: *mut u64,
    absolute_delta: *mut u64,
) -> i32 {
    let Some(length) = pixels.checked_mul(channels) else {
        return 1;
    };
    if length == 0
        || length > MAX_BYTES
        || length > isize::MAX as usize
        || left.is_null()
        || right.is_null()
        || changed_pixels.is_null()
        || absolute_delta.is_null()
        || !changed_pixels.is_aligned()
        || !absolute_delta.is_aligned()
        || changed_pixels == absolute_delta
    {
        return 1;
    }
    let result = std::panic::catch_unwind(|| {
        // SAFETY: bounds/null checks above plus the documented caller contract.
        let a = unsafe { std::slice::from_raw_parts(left, length) };
        let b = unsafe { std::slice::from_raw_parts(right, length) };
        frame_metrics_u8(a, b, channels)
    });
    match result {
        Ok(Ok(metrics)) => {
            // SAFETY: outputs have validated alignment; validity/non-overlap is
            // supplied by the caller. No input references escape the closure.
            unsafe {
                changed_pixels.write(metrics.changed_pixels);
                absolute_delta.write(metrics.absolute_delta);
            }
            0
        }
        Ok(Err(_)) => 1,
        Err(_) => 2,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_and_rgb_grouping() {
        assert_eq!(
            frame_metrics_u8(&[1, 2, 3], &[1, 2, 3], 3),
            Ok(Metrics {
                changed_pixels: 0,
                absolute_delta: 0,
            })
        );
        assert_eq!(
            frame_metrics_u8(&[0, 0, 0, 9, 9, 9], &[255, 1, 0, 9, 9, 9], 3),
            Ok(Metrics {
                changed_pixels: 1,
                absolute_delta: 256,
            })
        );
    }

    #[test]
    fn rejects_invalid_lengths_and_shapes() {
        assert_eq!(frame_metrics_u8(&[], &[], 1), Err(FrameError::InvalidShape));
        assert_eq!(frame_metrics_u8(&[0], &[0], 0), Err(FrameError::InvalidShape));
        assert_eq!(frame_metrics_u8(&[0], &[0], 2), Err(FrameError::InvalidShape));
        assert_eq!(
            frame_metrics_u8(&[0], &[0, 1], 1),
            Err(FrameError::InvalidLength)
        );
        let oversized = vec![0; MAX_BYTES + 1];
        assert_eq!(
            frame_metrics_u8(&oversized, &oversized, 1),
            Err(FrameError::InvalidLength)
        );
    }

    #[test]
    fn ffi_rejects_null_and_overflow_before_reading() {
        let mut changed = 7;
        let mut delta = 11;
        for (pixels, channels) in [(0, 1), (1, 0), (usize::MAX, 2), (1, 1)] {
            // SAFETY: invalid input is rejected before dereference; outputs are valid.
            let code = unsafe {
                cloudhime_frame_metrics_u8(
                    std::ptr::null(),
                    std::ptr::null(),
                    pixels,
                    channels,
                    &mut changed,
                    &mut delta,
                )
            };
            assert_eq!(code, 1);
            assert_eq!((changed, delta), (7, 11));
        }
    }

    #[test]
    fn ffi_agrees_with_safe_core() {
        let a = [0, 1, 2, 3];
        let b = [1, 1, 4, 3];
        let mut changed = 0;
        let mut delta = 0;
        // SAFETY: initialized arrays, matching lengths, distinct aligned outputs.
        let code = unsafe {
            cloudhime_frame_metrics_u8(a.as_ptr(), b.as_ptr(), 2, 2, &mut changed, &mut delta)
        };
        assert_eq!(code, 0);
        assert_eq!((changed, delta), (2, 3));
    }

    #[test]
    fn exhaustive_single_channel_byte_pairs() {
        for a in 0..=255_u8 {
            for b in 0..=255_u8 {
                let metrics = frame_metrics_u8(&[a], &[b], 1).unwrap();
                assert_eq!(metrics.changed_pixels, u64::from(a != b));
                assert_eq!(metrics.absolute_delta, u64::from(a.abs_diff(b)));
            }
        }
    }
}
