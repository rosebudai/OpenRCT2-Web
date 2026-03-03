/*****************************************************************************
 * Copyright (c) 2014-2026 OpenRCT2 developers
 *
 * For a complete list of all authors, please refer to contributors.md
 * Interested in contributing? Visit https://github.com/OpenRCT2/OpenRCT2
 *
 * OpenRCT2 is licensed under the GNU General Public License version 3.
 *****************************************************************************/

#pragma once

#include <SDL.h>
#include <array>
#include <cstdint>
#include <openrct2/Input.h>
#include <openrct2/world/Location.hpp>

namespace OpenRCT2::Ui
{
    enum class TouchGestureState
    {
        Idle,
        PossibleTap,
        Dragging,
        LongPress,
        Pinching,
        Rotating,
    };

    struct FingerInfo
    {
        SDL_FingerID id;
        ScreenCoordsXY startPos;
        ScreenCoordsXY currentPos;
        uint32_t downTimestamp;
    };

    class TouchGestureManager
    {
    private:
        TouchGestureState _state = TouchGestureState::Idle;
        std::array<FingerInfo, 2> _fingers;
        int _fingerCount = 0;
        bool _tapOnWidget = false;
        float _initialPinchDistance;
        float _initialPinchAngle;
        float _accumulatedRotation;
        int32_t _width;
        int32_t _height;
        uint32_t _lastTapTimestamp = 0;
        ScreenCoordsXY _lastTapPos;
        CursorState* _cursorState = nullptr;

        ScreenCoordsXY ToScreenCoords(float x, float y) const;
        bool IsOnWidget(const ScreenCoordsXY& pos) const;
        void EmitTap(const ScreenCoordsXY& pos);
        void EmitRightClick(const ScreenCoordsXY& pos);
        void EmitPanStart(const ScreenCoordsXY& pos);
        void EmitPanMove(const ScreenCoordsXY& pos);
        void EmitPanEnd(const ScreenCoordsXY& pos);
        void EmitDragStart(const ScreenCoordsXY& pos);
        void EmitDragMove(const ScreenCoordsXY& pos);
        void EmitDragEnd(const ScreenCoordsXY& pos);
        float GetPinchDistance() const;
        float GetPinchAngle() const;
        void Reset();

    public:
        explicit TouchGestureManager(CursorState* cursorState);

        void HandleFingerDown(const SDL_TouchFingerEvent& e);
        void HandleFingerUp(const SDL_TouchFingerEvent& e);
        void HandleFingerMotion(const SDL_TouchFingerEvent& e);
        void Update(uint32_t currentTicks);
        void SetScreenSize(int32_t width, int32_t height);
    };
} // namespace OpenRCT2::Ui
