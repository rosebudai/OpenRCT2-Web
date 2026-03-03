/*****************************************************************************
 * Copyright (c) 2014-2026 OpenRCT2 developers
 *
 * For a complete list of all authors, please refer to contributors.md
 * Interested in contributing? Visit https://github.com/OpenRCT2/OpenRCT2
 *
 * OpenRCT2 is licensed under the GNU General Public License version 3.
 *****************************************************************************/

#include "TouchGestureManager.h"

#include "MouseInput.h"

#include <cmath>
#include <openrct2-ui/interface/Window.h>
#include <openrct2/interface/Viewport.h>
#include <openrct2/ui/WindowManager.h>

using namespace OpenRCT2;
using namespace OpenRCT2::Ui;

// Constants
static constexpr int32_t kDragThresholdPx = 8;
static constexpr uint32_t kLongPressTimeoutMs = 500;
static constexpr uint32_t kDoubleTapTimeoutMs = 300;
static constexpr float kRotationThresholdDeg = 30.0f;
static constexpr int32_t kPinchZoomThresholdPx = 64;

TouchGestureManager::TouchGestureManager(CursorState* cursorState)
    : _state(TouchGestureState::Idle)
    , _fingers{}
    , _fingerCount(0)
    , _tapOnWidget(false)
    , _initialPinchDistance(0.0f)
    , _initialPinchAngle(0.0f)
    , _accumulatedRotation(0.0f)
    , _width(0)
    , _height(0)
    , _lastTapTimestamp(0)
    , _lastTapPos{}
    , _cursorState(cursorState)
{
}

ScreenCoordsXY TouchGestureManager::ToScreenCoords(float x, float y) const
{
    // SDL finger coordinates are normalized [0,1]. _width/_height are already
    // in game coordinates (native pixels / windowScale), so just multiply.
    auto screenX = static_cast<int32_t>(x * _width);
    auto screenY = static_cast<int32_t>(y * _height);
    return { screenX, screenY };
}

bool TouchGestureManager::IsOnWidget(const ScreenCoordsXY& pos) const
{
    auto* windowMgr = GetWindowManager();
    auto* window = windowMgr->FindFromPoint(pos);
    if (window == nullptr)
        return false;

    // If the touch point falls on a viewport, treat it as the map, not a widget.
    // This ensures one-finger drag on the map pans instead of left-click dragging.
    auto* viewport = ViewportFindFromPoint(pos);
    return (viewport == nullptr);
}

float TouchGestureManager::GetPinchDistance() const
{
    auto dx = static_cast<float>(_fingers[0].currentPos.x - _fingers[1].currentPos.x);
    auto dy = static_cast<float>(_fingers[0].currentPos.y - _fingers[1].currentPos.y);
    return std::sqrt(dx * dx + dy * dy);
}

float TouchGestureManager::GetPinchAngle() const
{
    auto dx = static_cast<float>(_fingers[1].currentPos.x - _fingers[0].currentPos.x);
    auto dy = static_cast<float>(_fingers[1].currentPos.y - _fingers[0].currentPos.y);
    return std::atan2(dy, dx) * 180.0f / 3.14159265358979323846f;
}

void TouchGestureManager::Reset()
{
    _state = TouchGestureState::Idle;
    _fingerCount = 0;
    _tapOnWidget = false;
    _initialPinchDistance = 0.0f;
    _initialPinchAngle = 0.0f;
    _accumulatedRotation = 0.0f;
}

void TouchGestureManager::SetScreenSize(int32_t width, int32_t height)
{
    _width = width;
    _height = height;
}

void TouchGestureManager::HandleFingerDown(const SDL_TouchFingerEvent& e)
{
    if (_fingerCount >= 2)
        return;

    auto pos = ToScreenCoords(e.x, e.y);

    // Store finger info
    _fingers[_fingerCount].id = e.fingerId;
    _fingers[_fingerCount].startPos = pos;
    _fingers[_fingerCount].currentPos = pos;
    _fingers[_fingerCount].downTimestamp = e.timestamp;
    _fingerCount++;

    if (_fingerCount == 1)
    {
        _state = TouchGestureState::PossibleTap;
        _tapOnWidget = IsOnWidget(pos);
        _cursorState->position = pos;

        if (_tapOnWidget)
        {
            // Widget interactions need press-on-down for responsiveness
            EmitDragStart(pos);
        }
    }
    else if (_fingerCount == 2)
    {
        // Transition to pinch/rotate mode
        if (_state == TouchGestureState::Dragging)
        {
            if (_tapOnWidget)
                EmitDragEnd(_fingers[0].currentPos);
            else
                EmitPanEnd(_fingers[0].currentPos);
        }
        else if (_state == TouchGestureState::PossibleTap && _tapOnWidget)
        {
            // Cancel the widget press
            EmitDragEnd(_fingers[0].currentPos);
        }

        _initialPinchDistance = GetPinchDistance();
        _initialPinchAngle = GetPinchAngle();
        _accumulatedRotation = 0.0f;
        _state = TouchGestureState::Pinching;
    }
}

void TouchGestureManager::HandleFingerUp(const SDL_TouchFingerEvent& e)
{
    // Find which finger was released
    int fingerIndex = -1;
    for (int i = 0; i < _fingerCount; i++)
    {
        if (_fingers[i].id == e.fingerId)
        {
            fingerIndex = i;
            break;
        }
    }
    if (fingerIndex < 0)
        return;

    auto pos = ToScreenCoords(e.x, e.y);

    switch (_state)
    {
        case TouchGestureState::PossibleTap:
        {
            // Check for double-tap
            auto timeSinceLastTap = e.timestamp - _lastTapTimestamp;
            auto dx = pos.x - _lastTapPos.x;
            auto dy = pos.y - _lastTapPos.y;
            auto distFromLastTap = std::sqrt(static_cast<float>(dx * dx + dy * dy));

            if (_lastTapTimestamp > 0 && timeSinceLastTap < kDoubleTapTimeoutMs
                && distFromLastTap < kDragThresholdPx)
            {
                // Double-tap → zoom in
                if (_tapOnWidget)
                    EmitDragEnd(pos);
                Windows::MainWindowZoom(true, true);
                _lastTapTimestamp = 0;
            }
            else
            {
                // Single tap
                if (_tapOnWidget)
                {
                    // Press was already sent on finger-down, just send release
                    EmitDragEnd(pos);
                }
                else
                {
                    EmitTap(pos);
                }
                _lastTapTimestamp = e.timestamp;
                _lastTapPos = pos;
            }
            break;
        }
        case TouchGestureState::Dragging:
        {
            if (_tapOnWidget)
                EmitDragEnd(pos);
            else
                EmitPanEnd(pos);
            break;
        }
        case TouchGestureState::LongPress:
        {
            // Right-click was already emitted by Update(), nothing more to do
            break;
        }
        case TouchGestureState::Pinching:
        case TouchGestureState::Rotating:
        {
            // Remove the lifted finger, keep the other
            // If one finger remains, go back to Idle rather than trying to
            // re-enter single-finger mode (avoids confusing state)
            break;
        }
        default:
            break;
    }

    // Remove the finger from the array
    if (fingerIndex < _fingerCount - 1)
    {
        _fingers[fingerIndex] = _fingers[_fingerCount - 1];
    }
    _fingerCount--;

    if (_fingerCount == 0)
    {
        _state = TouchGestureState::Idle;
    }
    else if (_fingerCount == 1 && (_state == TouchGestureState::Pinching || _state == TouchGestureState::Rotating))
    {
        // Dropped from 2 fingers to 1 — go idle to avoid accidental gestures
        _state = TouchGestureState::Idle;
    }
}

void TouchGestureManager::HandleFingerMotion(const SDL_TouchFingerEvent& e)
{
    // Find which finger moved
    int fingerIndex = -1;
    for (int i = 0; i < _fingerCount; i++)
    {
        if (_fingers[i].id == e.fingerId)
        {
            fingerIndex = i;
            break;
        }
    }
    if (fingerIndex < 0)
        return;

    auto pos = ToScreenCoords(e.x, e.y);
    _fingers[fingerIndex].currentPos = pos;

    switch (_state)
    {
        case TouchGestureState::PossibleTap:
        {
            auto dx = pos.x - _fingers[0].startPos.x;
            auto dy = pos.y - _fingers[0].startPos.y;
            auto dist = std::sqrt(static_cast<float>(dx * dx + dy * dy));

            if (dist > kDragThresholdPx)
            {
                _state = TouchGestureState::Dragging;
                if (_tapOnWidget)
                {
                    // Already sent press on finger-down, just move
                    EmitDragMove(pos);
                }
                else
                {
                    EmitPanStart(_fingers[0].startPos);
                    EmitPanMove(pos);
                }
            }
            else
            {
                // Still within threshold — update cursor position
                _cursorState->position = pos;
            }
            break;
        }
        case TouchGestureState::Dragging:
        {
            if (_tapOnWidget)
                EmitDragMove(pos);
            else
                EmitPanMove(pos);
            break;
        }
        case TouchGestureState::Pinching:
        {
            // Zoom: compare current pinch distance to initial
            float currentDist = GetPinchDistance();
            float diff = currentDist - _initialPinchDistance;
            if (std::abs(diff) > kPinchZoomThresholdPx)
            {
                Windows::MainWindowZoom(diff > 0, true);
                _initialPinchDistance = currentDist;
            }

            // Rotation: track angular change
            float currentAngle = GetPinchAngle();
            float angleDiff = currentAngle - _initialPinchAngle;

            // Normalize angle difference to [-180, 180]
            while (angleDiff > 180.0f)
                angleDiff -= 360.0f;
            while (angleDiff < -180.0f)
                angleDiff += 360.0f;

            _accumulatedRotation += angleDiff;
            _initialPinchAngle = currentAngle;

            if (std::abs(_accumulatedRotation) > kRotationThresholdDeg)
            {
                ViewportRotateAll(_accumulatedRotation > 0 ? 1 : -1);
                _accumulatedRotation = 0.0f;
            }
            break;
        }
        default:
            break;
    }
}

void TouchGestureManager::Update(uint32_t currentTicks)
{
    if (_state == TouchGestureState::PossibleTap && !_tapOnWidget && _fingerCount == 1)
    {
        if (currentTicks - _fingers[0].downTimestamp > kLongPressTimeoutMs)
        {
            _state = TouchGestureState::LongPress;
            EmitRightClick(_fingers[0].currentPos);
        }
    }
}

// Emit helpers — interface with the existing input system

void TouchGestureManager::EmitTap(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
    StoreMouseInput(MouseState::leftPress, pos);
    _cursorState->left = CURSOR_PRESSED;
    _cursorState->old = 1;
    StoreMouseInput(MouseState::leftRelease, pos);
    _cursorState->left = CURSOR_RELEASED;
    _cursorState->old = 3;
}

void TouchGestureManager::EmitRightClick(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
    StoreMouseInput(MouseState::rightPress, pos);
    _cursorState->right = CURSOR_PRESSED;
    _cursorState->old = 2;
    StoreMouseInput(MouseState::rightRelease, pos);
    _cursorState->right = CURSOR_RELEASED;
    _cursorState->old = 4;
}

void TouchGestureManager::EmitPanStart(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
    StoreMouseInput(MouseState::rightPress, pos);
    _cursorState->right = CURSOR_PRESSED;
    _cursorState->old = 2;
}

void TouchGestureManager::EmitPanMove(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
}

void TouchGestureManager::EmitPanEnd(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
    StoreMouseInput(MouseState::rightRelease, pos);
    _cursorState->right = CURSOR_RELEASED;
    _cursorState->old = 4;
}

void TouchGestureManager::EmitDragStart(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
    StoreMouseInput(MouseState::leftPress, pos);
    _cursorState->left = CURSOR_PRESSED;
    _cursorState->old = 1;
}

void TouchGestureManager::EmitDragMove(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
}

void TouchGestureManager::EmitDragEnd(const ScreenCoordsXY& pos)
{
    _cursorState->position = pos;
    _cursorState->touch = true;
    StoreMouseInput(MouseState::leftRelease, pos);
    _cursorState->left = CURSOR_RELEASED;
    _cursorState->old = 3;
}
